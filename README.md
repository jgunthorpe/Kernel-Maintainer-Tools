Prologue
========

This stuff needs python3. Comes with the distros I use. 

gj scripts
==========

These are helper scripts for git and other things I felt like automating.

Most useful:

check-patch
-----------

Automate running checkpatch for the kernel.

update-shared
-------------

Assume you have a .../shared/kernel.org.git which is a pristine copy of
Linus's tree and use 'git clone -s' from that - then update-shared goes to
that tree, downloads the latest from master then updates the local tree
origin/master to that same value.

Sort of like a 'git fetch' that is cached in the shared place.

edit-comments
-------------

Is like rebase but only for comments.  It directly, rapidly and non-invasively
lets you edit commit comments. Absolutely everything else stays the same about
the commits except for the commit ID, and it can work across merges

ko-ssh
------

Prompt for the 2FA value and open a write capable k.o ssh session. Assumes the
kernel.org account has 2FA enabled

review
------

For looking at gerrit stuff outside gerrit where it is fast. Make a diff
navigable by emacs and automate a few steps here.

reply-email/ack-emails
----------------------

Assuming you have a gmail account that gets all list emails these scripts use
it as a database to reply to specific messages. eg you can reply from a
patchworks thread using the patchworks message id. Searchs gmail, downloads
the messages and runs mutt.

ack-emails does the above automatically driven by applied patches and
patchworks bundle files.

Bit insane, but whatever. :|

linus-check-merge/linus-pull-request/ko-status/to-zero-day
----------------------------------------------------------

Support the k.o workflow Doug I and I use.
