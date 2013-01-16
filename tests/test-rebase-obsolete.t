==========================
Test rebase with obsolete
==========================

Enable obsolete

  $ cat > ${TESTTMP}/obs.py << EOF
  > import mercurial.obsolete
  > mercurial.obsolete._enabled = True
  > EOF
  $ cat >> $HGRCPATH << EOF
  > [ui]
  > logtemplate= {rev}:{node|short} {desc|firstline}
  > [phases]
  > publish=False
  > [extensions]'
  > rebase=
  > 
  > obs=${TESTTMP}/obs.py
  > EOF

Setup rebase canonical repo

  $ hg init base
  $ cd base
  $ hg unbundle "$TESTDIR/bundles/rebase.hg"
  adding changesets
  adding manifests
  adding file changes
  added 8 changesets with 7 changes to 7 files (+2 heads)
  (run 'hg heads' to see heads, 'hg merge' to merge)
  $ hg up tip
  3 files updated, 0 files merged, 0 files removed, 0 files unresolved
  $ hg log -G
  @  7:02de42196ebe H
  |
  | o  6:eea13746799a G
  |/|
  o |  5:24b6387c8c8c F
  | |
  | o  4:9520eea781bc E
  |/
  | o  3:32af7686d403 D
  | |
  | o  2:5fddd98957c8 C
  | |
  | o  1:42ccdea3bb16 B
  |/
  o  0:cd010b8cd998 A
  
  $ cd ..

simple rebase
---------------------------------

  $ hg clone base simple
  updating to branch default
  3 files updated, 0 files merged, 0 files removed, 0 files unresolved
  $ cd simple
  $ hg up 32af7686d403
  3 files updated, 0 files merged, 2 files removed, 0 files unresolved
  $ hg rebase -d eea13746799a
  $ hg log -G
  @  10:8eeb3c33ad33 D
  |
  o  9:2327fea05063 C
  |
  o  8:e4e5be0395b2 B
  |
  | o  7:02de42196ebe H
  | |
  o |  6:eea13746799a G
  |\|
  | o  5:24b6387c8c8c F
  | |
  o |  4:9520eea781bc E
  |/
  o  0:cd010b8cd998 A
  
  $ hg log --hidden -G
  @  10:8eeb3c33ad33 D
  |
  o  9:2327fea05063 C
  |
  o  8:e4e5be0395b2 B
  |
  | o  7:02de42196ebe H
  | |
  o |  6:eea13746799a G
  |\|
  | o  5:24b6387c8c8c F
  | |
  o |  4:9520eea781bc E
  |/
  | x  3:32af7686d403 D
  | |
  | x  2:5fddd98957c8 C
  | |
  | x  1:42ccdea3bb16 B
  |/
  o  0:cd010b8cd998 A
  
  $ hg debugobsolete
  42ccdea3bb16d28e1848c95fe2e44c000f3f21b1 e4e5be0395b2cbd471ed22a26b1b6a1a0658a794 0 {'date': '*', 'user': 'test'} (glob)
  5fddd98957c8a54a4d436dfe1da9d87f21a1b97b 2327fea05063f39961b14cb69435a9898dc9a245 0 {'date': '*', 'user': 'test'} (glob)
  32af7686d403cf45b5d95f2d70cebea587ac806a 8eeb3c33ad33d452c89e5dcf611c347f978fb42b 0 {'date': '*', 'user': 'test'} (glob)


  $ cd ..

empty changeset
---------------------------------

  $ hg clone base empty
  updating to branch default
  3 files updated, 0 files merged, 0 files removed, 0 files unresolved
  $ cd empty
  $ hg up eea13746799a
  1 files updated, 0 files merged, 1 files removed, 0 files unresolved

We make a copy of both the first changeset in the rebased and some other in the
set.

  $ hg graft 42ccdea3bb16 32af7686d403
  grafting revision 1
  grafting revision 3
  $ hg rebase  -s 42ccdea3bb16 -d .
  $ hg log -G
  @  10:5ae4c968c6ac C
  |
  o  9:08483444fef9 D
  |
  o  8:8877864f1edb B
  |
  | o  7:02de42196ebe H
  | |
  o |  6:eea13746799a G
  |\|
  | o  5:24b6387c8c8c F
  | |
  o |  4:9520eea781bc E
  |/
  o  0:cd010b8cd998 A
  
  $ hg log --hidden -G
  @  10:5ae4c968c6ac C
  |
  o  9:08483444fef9 D
  |
  o  8:8877864f1edb B
  |
  | o  7:02de42196ebe H
  | |
  o |  6:eea13746799a G
  |\|
  | o  5:24b6387c8c8c F
  | |
  o |  4:9520eea781bc E
  |/
  | x  3:32af7686d403 D
  | |
  | x  2:5fddd98957c8 C
  | |
  | x  1:42ccdea3bb16 B
  |/
  o  0:cd010b8cd998 A
  
  $ hg debugobsolete
  42ccdea3bb16d28e1848c95fe2e44c000f3f21b1 08483444fef91d6224f6655ee586a65d263ad34c 0 {'date': '*', 'user': 'test'} (glob)
  5fddd98957c8a54a4d436dfe1da9d87f21a1b97b 5ae4c968c6aca831df823664e706c9d4aa34473d 0 {'date': '*', 'user': 'test'} (glob)
  32af7686d403cf45b5d95f2d70cebea587ac806a 5ae4c968c6aca831df823664e706c9d4aa34473d 0 {'date': '*', 'user': 'test'} (glob)


  $ cd ..

collapse rebase
---------------------------------

  $ hg clone base collapse
  updating to branch default
  3 files updated, 0 files merged, 0 files removed, 0 files unresolved
  $ cd collapse
  $ hg rebase  -s 42ccdea3bb16 -d eea13746799a --collapse
  $ hg log -G
  @  8:4dc2197e807b Collapsed revision
  |
  | o  7:02de42196ebe H
  | |
  o |  6:eea13746799a G
  |\|
  | o  5:24b6387c8c8c F
  | |
  o |  4:9520eea781bc E
  |/
  o  0:cd010b8cd998 A
  
  $ hg log --hidden -G
  @  8:4dc2197e807b Collapsed revision
  |
  | o  7:02de42196ebe H
  | |
  o |  6:eea13746799a G
  |\|
  | o  5:24b6387c8c8c F
  | |
  o |  4:9520eea781bc E
  |/
  | x  3:32af7686d403 D
  | |
  | x  2:5fddd98957c8 C
  | |
  | x  1:42ccdea3bb16 B
  |/
  o  0:cd010b8cd998 A
  
  $ hg id --debug
  4dc2197e807bae9817f09905b50ab288be2dbbcf tip
  $ hg debugobsolete
  42ccdea3bb16d28e1848c95fe2e44c000f3f21b1 4dc2197e807bae9817f09905b50ab288be2dbbcf 0 {'date': '*', 'user': 'test'} (glob)
  5fddd98957c8a54a4d436dfe1da9d87f21a1b97b 4dc2197e807bae9817f09905b50ab288be2dbbcf 0 {'date': '*', 'user': 'test'} (glob)
  32af7686d403cf45b5d95f2d70cebea587ac806a 4dc2197e807bae9817f09905b50ab288be2dbbcf 0 {'date': '*', 'user': 'test'} (glob)

  $ cd ..

Rebase set has hidden descendants
---------------------------------

We rebase a changeset which has a hidden changeset. The hidden changeset must
not be rebased.

  $ hg clone base hidden
  updating to branch default
  3 files updated, 0 files merged, 0 files removed, 0 files unresolved
  $ cd hidden
  $ hg rebase -s 5fddd98957c8 -d eea13746799a
  $ hg rebase -s 42ccdea3bb16 -d 02de42196ebe
  $ hg log -G
  @  10:7c6027df6a99 B
  |
  | o  9:cf44d2f5a9f4 D
  | |
  | o  8:e273c5e7d2d2 C
  | |
  o |  7:02de42196ebe H
  | |
  | o  6:eea13746799a G
  |/|
  o |  5:24b6387c8c8c F
  | |
  | o  4:9520eea781bc E
  |/
  o  0:cd010b8cd998 A
  
  $ hg log --hidden -G
  @  10:7c6027df6a99 B
  |
  | o  9:cf44d2f5a9f4 D
  | |
  | o  8:e273c5e7d2d2 C
  | |
  o |  7:02de42196ebe H
  | |
  | o  6:eea13746799a G
  |/|
  o |  5:24b6387c8c8c F
  | |
  | o  4:9520eea781bc E
  |/
  | x  3:32af7686d403 D
  | |
  | x  2:5fddd98957c8 C
  | |
  | x  1:42ccdea3bb16 B
  |/
  o  0:cd010b8cd998 A
  
  $ hg debugobsolete
  5fddd98957c8a54a4d436dfe1da9d87f21a1b97b e273c5e7d2d29df783dce9f9eaa3ac4adc69c15d 0 {'date': '*', 'user': 'test'} (glob)
  32af7686d403cf45b5d95f2d70cebea587ac806a cf44d2f5a9f4297a62be94cbdd3dff7c7dc54258 0 {'date': '*', 'user': 'test'} (glob)
  42ccdea3bb16d28e1848c95fe2e44c000f3f21b1 7c6027df6a99d93f461868e5433f63bde20b6dfb 0 {'date': '*', 'user': 'test'} (glob)

Test that rewriting leaving instability behind is allowed
---------------------------------------------------------------------

  $ hg log -r 'children(8)'
  9:cf44d2f5a9f4 D (no-eol)
  $ hg rebase -r 8
  $ hg log -G
  @  11:0d8f238b634c C
  |
  o  10:7c6027df6a99 B
  |
  | o  9:cf44d2f5a9f4 D
  | |
  | x  8:e273c5e7d2d2 C
  | |
  o |  7:02de42196ebe H
  | |
  | o  6:eea13746799a G
  |/|
  o |  5:24b6387c8c8c F
  | |
  | o  4:9520eea781bc E
  |/
  o  0:cd010b8cd998 A
  


Test multiple root handling
------------------------------------

  $ hg rebase --dest 4 --rev '7+11+9'
  $ hg log -G
  @  14:00891d85fcfc C
  |
  | o  13:102b4c1d889b D
  |/
  | o  12:bfe264faf697 H
  |/
  | o  10:7c6027df6a99 B
  | |
  | x  7:02de42196ebe H
  | |
  +---o  6:eea13746799a G
  | |/
  | o  5:24b6387c8c8c F
  | |
  o |  4:9520eea781bc E
  |/
  o  0:cd010b8cd998 A
  
