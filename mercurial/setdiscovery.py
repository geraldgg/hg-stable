# setdiscovery.py - improved discovery of common nodeset for mercurial
#
# Copyright 2010 Benoit Boissinot <bboissin@gmail.com>
# and Peter Arrenbrecht <peter@arrenbrecht.ch>
#
# This software may be used and distributed according to the terms of the
# GNU General Public License version 2 or any later version.

from node import nullid
from i18n import _
import random, collections, util, dagutil

def _updatesample(dag, nodes, sample, always, quicksamplesize=0):
    # if nodes is empty we scan the entire graph
    if nodes:
        heads = dag.headsetofconnecteds(nodes)
    else:
        heads = dag.heads()
    dist = {}
    visit = collections.deque(heads)
    seen = set()
    factor = 1
    while visit:
        curr = visit.popleft()
        if curr in seen:
            continue
        d = dist.setdefault(curr, 1)
        if d > factor:
            factor *= 2
        if d == factor:
            if curr not in always: # need this check for the early exit below
                sample.add(curr)
                if quicksamplesize and (len(sample) >= quicksamplesize):
                    return
        seen.add(curr)
        for p in dag.parents(curr):
            if not nodes or p in nodes:
                dist.setdefault(p, d + 1)
                visit.append(p)

def _setupsample(dag, nodes, size):
    if len(nodes) <= size:
        return set(nodes), None, 0
    always = set(dag.heads())
    desiredlen = size - len(always)
    if desiredlen <= 0:
        # This could be bad if there are very many heads, all unknown to the
        # server. We're counting on long request support here.
        return always, None, desiredlen
    return always, set(), desiredlen

def _takequicksample(dag, nodes, size, initial):
    always, sample, desiredlen = _setupsample(dag, nodes, size)
    if sample is None:
        return always
    if initial:
        fromset = None
    else:
        fromset = nodes
    _updatesample(dag, fromset, sample, always, quicksamplesize=desiredlen)
    sample.update(always)
    return sample

def _takefullsample(dag, nodes, size):
    always, sample, desiredlen = _setupsample(dag, nodes, size)
    if sample is None:
        return always
    # update from heads
    _updatesample(dag, nodes, sample, always)
    # update from roots
    _updatesample(dag.inverse(), nodes, sample, always)
    assert sample
    if len(sample) > desiredlen:
        sample = set(random.sample(sample, desiredlen))
    elif len(sample) < desiredlen:
        more = desiredlen - len(sample)
        sample.update(random.sample(list(nodes - sample - always), more))
    sample.update(always)
    return sample

def findcommonheads(ui, local, remote,
                    initialsamplesize=100,
                    fullsamplesize=200,
                    abortwhenunrelated=True):
    '''Return a tuple (common, anyincoming, remoteheads) used to identify
    missing nodes from or in remote.

    shortcutlocal determines whether we try use direct access to localrepo if
    remote is actually local.
    '''
    roundtrips = 0
    cl = local.changelog
    dag = dagutil.revlogdag(cl)
    nodes = dag.nodeset()

    # early exit if we know all the specified server heads already
    ui.debug("query 1; heads\n")
    roundtrips += 1
    srvheadhashes = remote.heads()

    ## TODO We might want to request an additional random sample of the server's
    ## nodes batched with the heads query here.

    if cl.tip() == nullid:
        if srvheadhashes != [nullid]:
            return [nullid], True, srvheadhashes
        return [nullid], False, []

    # start actual discovery (we note this before the next "if" for
    # compatibility reasons)
    ui.status(_("searching for changes\n"))

    srvheads = dag.internalizeall(srvheadhashes, filterunknown=True)
    if len(srvheads) == len(srvheadhashes):
        ui.note("all remote heads known locally\n")
        return (srvheadhashes, False, srvheadhashes,)

    # full blown discovery
    undecided = nodes # own nodes where I don't know if the server knows them
    common = set() # own nodes I know we both know
    missing = set() # own nodes I know the server lacks

    # treat remote heads as a first implicit sample response
    common.update(dag.ancestorset(srvheads))
    undecided.difference_update(common)
    # use cheapish initial sample
    if common:
        ui.debug("taking initial sample\n")
        sample = _takefullsample(dag, undecided, size=fullsamplesize)
    else:
        ui.debug("taking quick initial sample\n")
        sample = _takequicksample(dag, nodes, size=initialsamplesize,
                                  initial=True)

    roundtrips += 1
    ui.progress(_('searching'), roundtrips, unit=_('queries'))
    ui.debug("query %i; still undecided: %i, sample size is: %i\n"
             % (roundtrips, len(undecided), len(sample)))
    # indices between sample and externalized version must match
    sample = list(sample)
    yesno = remote.known(dag.externalizeall(sample))

    while undecided:
        commoninsample = set(n for i, n in enumerate(sample) if yesno[i])
        common.update(dag.ancestorset(commoninsample, common))

        missinginsample = [n for i, n in enumerate(sample) if not yesno[i]]
        missing.update(dag.descendantset(missinginsample, missing))

        undecided.difference_update(missing)
        undecided.difference_update(common)

        if not undecided:
            break

        ui.note("sampling from both directions\n")
        sample = _takefullsample(dag, undecided, size=fullsamplesize)

        roundtrips += 1
        ui.progress(_('searching'), roundtrips, unit=_('queries'))
        ui.debug("query %i; still undecided: %i, sample size is: %i\n"
                 % (roundtrips, len(undecided), len(sample)))
        # indices between sample and externalized version must match
        sample = list(sample)
        yesno = remote.known(dag.externalizeall(sample))

    result = dag.headsetofconnecteds(common)
    ui.progress(_('searching'), None)
    ui.debug("%d total queries\n" % roundtrips)

    if not result and srvheadhashes != [nullid]:
        if abortwhenunrelated:
            raise util.Abort(_("repository is unrelated"))
        else:
            ui.warn(_("warning: repository is unrelated\n"))
        return (set([nullid]), True, srvheadhashes,)

    return (dag.externalizeall(result), True, srvheadhashes,)
