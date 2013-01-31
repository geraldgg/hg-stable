  $ cat >> $HGRCPATH <<EOF
  > [extensions]
  > graphlog=
  > rebase=
  > 
  > [phases]
  > publish=False
  > 
  > [alias]
  > tglog = log -G --template "{rev}: '{desc}' bookmarks: {bookmarks}\n"
  > EOF

Create a repo with several bookmarks
  $ hg init a
  $ cd a

  $ echo a > a
  $ hg ci -Am A
  adding a

  $ echo b > b
  $ hg ci -Am B
  adding b
  $ hg book 'X'
  $ hg book 'Y'

  $ echo c > c
  $ hg ci -Am C
  adding c
  $ hg book 'Z'

  $ hg up -q 0

  $ echo d > d
  $ hg ci -Am D
  adding d
  created new head

  $ hg book W

  $ hg tglog
  @  3: 'D' bookmarks: W
  |
  | o  2: 'C' bookmarks: Y Z
  | |
  | o  1: 'B' bookmarks: X
  |/
  o  0: 'A' bookmarks:
  

Move only rebased bookmarks

  $ cd ..
  $ hg clone -q a a1

  $ cd a1
  $ hg up -q Z

Test deleting divergent bookmarks from dest (issue3685)

  $ hg book -r 3 Z@diverge

... and also test that bookmarks not on dest or not being moved aren't deleted

  $ hg book -r 3 X@diverge
  $ hg book -r 0 Y@diverge

  $ hg tglog
  o  3: 'D' bookmarks: W X@diverge Z@diverge
  |
  | @  2: 'C' bookmarks: Y Z
  | |
  | o  1: 'B' bookmarks: X
  |/
  o  0: 'A' bookmarks: Y@diverge
  
  $ hg rebase -s Y -d 3
  saved backup bundle to $TESTTMP/a1/.hg/strip-backup/*-backup.hg (glob)

  $ hg tglog
  @  3: 'C' bookmarks: Y Z
  |
  o  2: 'D' bookmarks: W X@diverge
  |
  | o  1: 'B' bookmarks: X
  |/
  o  0: 'A' bookmarks: Y@diverge
  
Keep bookmarks to the correct rebased changeset

  $ cd ..
  $ hg clone -q a a2

  $ cd a2
  $ hg up -q Z

  $ hg rebase -s 1 -d 3
  saved backup bundle to $TESTTMP/a2/.hg/strip-backup/*-backup.hg (glob)

  $ hg tglog
  @  3: 'C' bookmarks: Y Z
  |
  o  2: 'B' bookmarks: X
  |
  o  1: 'D' bookmarks: W
  |
  o  0: 'A' bookmarks:
  

Keep active bookmark on the correct changeset

  $ cd ..
  $ hg clone -q a a3

  $ cd a3
  $ hg up -q X

  $ hg rebase -d W
  saved backup bundle to $TESTTMP/a3/.hg/strip-backup/*-backup.hg (glob)

  $ hg tglog
  @  3: 'C' bookmarks: Y Z
  |
  o  2: 'B' bookmarks: X
  |
  o  1: 'D' bookmarks: W
  |
  o  0: 'A' bookmarks:
  

  $ cd ..
