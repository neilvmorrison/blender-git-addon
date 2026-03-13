# Git Operations

This addon is not targeted towards power-users. Instead, our guiding principle is to make the git protocol accessible to the average Blender user so that they can leverage a subset of its capabilities. We'll expand as necessary.

## Primary Operations

Users must be able to:

1. Initialize a git repository with an appropriate .gitignore
2. CRUD and checkout branches
3. Create commits on branches
4. Manage their commit history to prune old and unused binaries that are being version-controlled.

We need to create methods to perform these operations so that they can be called from the GUI

At all times, we must avoid floating changes in the binaries so that we don't encounter conflicts between branching operations since we can't diff binary files.
