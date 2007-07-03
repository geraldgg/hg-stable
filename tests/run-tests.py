#!/usr/bin/env python
#
# run-tests.py - Run a set of tests on Mercurial
#
# Copyright 2006 Matt Mackall <mpm@selenic.com>
#
# This software may be used and distributed according to the terms
# of the GNU General Public License, incorporated herein by reference.

import difflib
import errno
import optparse
import os
import popen2
import re
import shutil
import signal
import sys
import tempfile
import time

required_tools = ["python", "diff", "grep", "unzip", "gunzip", "bunzip2", "sed"]

parser = optparse.OptionParser("%prog [options] [tests]")
parser.add_option("-v", "--verbose", action="store_true",
    help="output verbose messages")
parser.add_option("-t", "--timeout", type="int",
    help="kill errant tests after TIMEOUT seconds")
parser.add_option("-c", "--cover", action="store_true",
    help="print a test coverage report")
parser.add_option("-s", "--cover_stdlib", action="store_true",
    help="print a test coverage report inc. standard libraries")
parser.add_option("-C", "--annotate", action="store_true",
    help="output files annotated with coverage")
parser.add_option("-r", "--retest", action="store_true",
    help="retest failed tests")
parser.add_option("-f", "--first", action="store_true",
    help="exit on the first test failure")
parser.add_option("-R", "--restart", action="store_true",
    help="restart at last error")
parser.add_option("-i", "--interactive", action="store_true",
    help="prompt to accept changed output")

parser.set_defaults(timeout=180)
(options, args) = parser.parse_args()
verbose = options.verbose
coverage = options.cover or options.cover_stdlib or options.annotate
python = sys.executable

def vlog(*msg):
    if verbose:
        for m in msg:
            print m,
        print

def splitnewlines(text):
    '''like str.splitlines, but only split on newlines.
    keep line endings.'''
    i = 0
    lines = []
    while True:
        n = text.find('\n', i)
        if n == -1:
            last = text[i:]
            if last:
                lines.append(last)
            return lines
        lines.append(text[i:n+1])
        i = n + 1

def show_diff(expected, output):
    for line in difflib.unified_diff(expected, output,
            "Expected output", "Test output"):
        sys.stdout.write(line)

def find_program(program):
    """Search PATH for a executable program"""
    for p in os.environ.get('PATH', os.defpath).split(os.pathsep):
        name = os.path.join(p, program)
        if os.access(name, os.X_OK):
            return name
    return None

def check_required_tools():
    # Before we go any further, check for pre-requisite tools
    # stuff from coreutils (cat, rm, etc) are not tested
    for p in required_tools:
        if os.name == 'nt':
            p += '.exe'
        found = find_program(p)
        if found:
            vlog("# Found prerequisite", p, "at", found)
        else:
            print "WARNING: Did not find prerequisite tool: "+p

def cleanup_exit():
    if verbose:
        print "# Cleaning up HGTMP", HGTMP
    shutil.rmtree(HGTMP, True)

def use_correct_python():
    # some tests run python interpreter. they must use same
    # interpreter we use or bad things will happen.
    exedir, exename = os.path.split(sys.executable)
    if exename == 'python':
        path = find_program('python')
        if os.path.dirname(path) == exedir:
            return
    vlog('# Making python executable in test path use correct Python')
    my_python = os.path.join(BINDIR, 'python')
    try:
        os.symlink(sys.executable, my_python)
    except AttributeError:
        # windows fallback
        shutil.copyfile(sys.executable, my_python)
        shutil.copymode(sys.executable, my_python)

def install_hg():
    global python
    vlog("# Performing temporary installation of HG")
    installerrs = os.path.join("tests", "install.err")

    os.chdir("..") # Get back to hg root
    cmd = ('%s setup.py clean --all'
           ' install --force --home="%s" --install-lib="%s" >%s 2>&1'
           % (sys.executable, INST, PYTHONDIR, installerrs))
    vlog("# Running", cmd)
    if os.system(cmd) == 0:
        if not verbose:
            os.remove(installerrs)
    else:
        f = open(installerrs)
        for line in f:
            print line,
        f.close()
        sys.exit(1)
    os.chdir(TESTDIR)

    os.environ["PATH"] = "%s%s%s" % (BINDIR, os.pathsep, os.environ["PATH"])
    os.environ["PYTHONPATH"] = PYTHONDIR

    use_correct_python()

    if coverage:
        vlog("# Installing coverage wrapper")
        os.environ['COVERAGE_FILE'] = COVERAGE_FILE
        if os.path.exists(COVERAGE_FILE):
            os.unlink(COVERAGE_FILE)
        # Create a wrapper script to invoke hg via coverage.py
        os.rename(os.path.join(BINDIR, "hg"), os.path.join(BINDIR, "_hg.py"))
        f = open(os.path.join(BINDIR, 'hg'), 'w')
        f.write('#!' + sys.executable + '\n')
        f.write('import sys, os; os.execv(sys.executable, [sys.executable, '
                '"%s", "-x", "%s"] + sys.argv[1:])\n' %
                (os.path.join(TESTDIR, 'coverage.py'),
                 os.path.join(BINDIR, '_hg.py')))
        f.close()
        os.chmod(os.path.join(BINDIR, 'hg'), 0700)
        python = '"%s" "%s" -x' % (sys.executable,
                                   os.path.join(TESTDIR,'coverage.py'))

def output_coverage():
    vlog("# Producing coverage report")
    omit = [BINDIR, TESTDIR, PYTHONDIR]
    if not options.cover_stdlib:
        # Exclude as system paths (ignoring empty strings seen on win)
        omit += [x for x in sys.path if x != '']
    omit = ','.join(omit)
    os.chdir(PYTHONDIR)
    cmd = '"%s" "%s" -i -r "--omit=%s"' % (
        sys.executable, os.path.join(TESTDIR, 'coverage.py'), omit)
    vlog("# Running: "+cmd)
    os.system(cmd)
    if options.annotate:
        adir = os.path.join(TESTDIR, 'annotated')
        if not os.path.isdir(adir):
            os.mkdir(adir)
        cmd = '"%s" "%s" -i -a "--directory=%s" "--omit=%s"' % (
            sys.executable, os.path.join(TESTDIR, 'coverage.py'),
            adir, omit)
        vlog("# Running: "+cmd)
        os.system(cmd)

class Timeout(Exception):
    pass

def alarmed(signum, frame):
    raise Timeout

def run(cmd):
    """Run command in a sub-process, capturing the output (stdout and stderr).
    Return the exist code, and output."""
    # TODO: Use subprocess.Popen if we're running on Python 2.4
    if os.name == 'nt':
        tochild, fromchild = os.popen4(cmd)
        tochild.close()
        output = fromchild.read()
        ret = fromchild.close()
        if ret == None:
            ret = 0
    else:
        proc = popen2.Popen4(cmd)
        try:
            output = ''
            proc.tochild.close()
            output = proc.fromchild.read()
            ret = proc.wait()
        except Timeout:
            vlog('# Process %d timed out - killing it' % proc.pid)
            os.kill(proc.pid, signal.SIGTERM)
            ret = proc.wait()
            if ret == 0:
                ret = signal.SIGTERM << 8
    return ret, splitnewlines(output)

def run_one(test):
    '''tristate output:
    None -> skipped
    True -> passed
    False -> failed'''

    vlog("# Test", test)
    if not verbose:
        sys.stdout.write('.')
        sys.stdout.flush()

    # create a fresh hgrc
    hgrc = file(HGRCPATH, 'w+')
    hgrc.write('[ui]\n')
    hgrc.write('slash = True\n')
    hgrc.close()

    err = os.path.join(TESTDIR, test+".err")
    ref = os.path.join(TESTDIR, test+".out")
    testpath = os.path.join(TESTDIR, test)

    if os.path.exists(err):
        os.remove(err)       # Remove any previous output files

    # Make a tmp subdirectory to work in
    tmpd = os.path.join(HGTMP, test)
    os.mkdir(tmpd)
    os.chdir(tmpd)

    try:
        tf = open(testpath)
        firstline = tf.readline().rstrip()
        tf.close()
    except:
        firstline = ''
    lctest = test.lower()

    if lctest.endswith('.py') or firstline == '#!/usr/bin/env python':
        cmd = '%s "%s"' % (python, testpath)
    elif lctest.endswith('.bat'):
        # do not run batch scripts on non-windows
        if os.name != 'nt':
            print '\nSkipping %s: batch script' % test
            return None
        # To reliably get the error code from batch files on WinXP,
        # the "cmd /c call" prefix is needed. Grrr
        cmd = 'cmd /c call "%s"' % testpath
    else:
        # do not run shell scripts on windows
        if os.name == 'nt':
            print '\nSkipping %s: shell script' % test
            return None
        # do not try to run non-executable programs
        if not os.access(testpath, os.X_OK):
            print '\nSkipping %s: not executable' % test
            return None
        cmd = '"%s"' % testpath

    if options.timeout > 0:
        signal.alarm(options.timeout)

    vlog("# Running", cmd)
    ret, out = run(cmd)
    vlog("# Ret was:", ret)

    if options.timeout > 0:
        signal.alarm(0)

    diffret = 0
    # If reference output file exists, check test output against it
    if os.path.exists(ref):
        f = open(ref, "r")
        ref_out = splitnewlines(f.read())
        f.close()
    else:
        ref_out = []
    if out != ref_out:
        diffret = 1
        print "\nERROR: %s output changed" % (test)
        show_diff(ref_out, out)
    if ret:
        print "\nERROR: %s failed with error code %d" % (test, ret)
    elif diffret:
        ret = diffret

    if ret != 0: # Save errors to a file for diagnosis
        f = open(err, "wb")
        for line in out:
            f.write(line)
        f.close()

    # Kill off any leftover daemon processes
    try:
        fp = file(DAEMON_PIDS)
        for line in fp:
            try:
                pid = int(line)
            except ValueError:
                continue
            try:
                os.kill(pid, 0)
                vlog('# Killing daemon process %d' % pid)
                os.kill(pid, signal.SIGTERM)
                time.sleep(0.25)
                os.kill(pid, 0)
                vlog('# Daemon process %d is stuck - really killing it' % pid)
                os.kill(pid, signal.SIGKILL)
            except OSError, err:
                if err.errno != errno.ESRCH:
                    raise
        fp.close()
        os.unlink(DAEMON_PIDS)
    except IOError:
        pass

    os.chdir(TESTDIR)
    shutil.rmtree(tmpd, True)
    return ret == 0


os.umask(022)

check_required_tools()

# Reset some environment variables to well-known values so that
# the tests produce repeatable output.
os.environ['LANG'] = os.environ['LC_ALL'] = 'C'
os.environ['TZ'] = 'GMT'

TESTDIR = os.environ["TESTDIR"] = os.getcwd()
HGTMP   = os.environ["HGTMP"]   = tempfile.mkdtemp("", "hgtests.")
DAEMON_PIDS = os.environ["DAEMON_PIDS"] = os.path.join(HGTMP, 'daemon.pids')
HGRCPATH = os.environ["HGRCPATH"] = os.path.join(HGTMP, '.hgrc')

os.environ["HGEDITOR"] = sys.executable + ' -c "import sys; sys.exit(0)"'
os.environ["HGMERGE"]  = ('python "%s" -L my -L other'
                          % os.path.join(TESTDIR, os.path.pardir, 'contrib',
                                         'simplemerge'))
os.environ["HGUSER"]   = "test"
os.environ["HGENCODING"] = "ascii"
os.environ["HGENCODINGMODE"] = "strict"

vlog("# Using TESTDIR", TESTDIR)
vlog("# Using HGTMP", HGTMP)

INST = os.path.join(HGTMP, "install")
BINDIR = os.path.join(INST, "bin")
PYTHONDIR = os.path.join(INST, "lib", "python")
COVERAGE_FILE = os.path.join(TESTDIR, ".coverage")

try:
    try:
        install_hg()

        if options.timeout > 0:
            try:
                signal.signal(signal.SIGALRM, alarmed)
                vlog('# Running tests with %d-second timeout' %
                     options.timeout)
            except AttributeError:
                print 'WARNING: cannot run tests with timeouts'
                options.timeout = 0

        tested = 0
        failed = 0
        skipped = 0

        if len(args) == 0:
            args = os.listdir(".")
            args.sort()


        tests = []
        for test in args:
            if (test.startswith("test-") and '~' not in test and
                ('.' not in test or test.endswith('.py') or
                 test.endswith('.bat'))):
                tests.append(test)

        if options.restart:
            orig = list(tests)
            while tests:
                if os.path.exists(tests[0] + ".err"):
                    break
                tests.pop(0)
            if not tests:
                print "running all tests"
                tests = orig

        for test in tests:
            if options.retest and not os.path.exists(test + ".err"):
                skipped += 1
                continue
            ret = run_one(test)
            if ret is None:
                skipped += 1
            elif not ret:
                if options.interactive:
                    print "Accept this change? [n] ",
                    answer = sys.stdin.readline().strip()
                    if answer.lower() in "y yes".split():
                        os.rename(test + ".err", test + ".out")
                        tested += 1
                        continue
                failed += 1
                if options.first:
                    break
            tested += 1

        print "\n# Ran %d tests, %d skipped, %d failed." % (tested, skipped,
                                                            failed)
        if coverage:
            output_coverage()
    except KeyboardInterrupt:
        failed = True
        print "\ninterrupted!"
finally:
    cleanup_exit()

if failed:
    sys.exit(1)
