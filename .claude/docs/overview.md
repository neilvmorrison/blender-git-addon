# Overview

This addon is a GUI for managing Blender projects using the Large File extension for the git protocol.

## Primary Workflow

Assuming the user is starting from zero, users shall be able to:

- Set a working directory to house all of their projects (global config, settable in addon settings)
  - (maybe later) would be cool to also create a remote directory in whichever hosted service user wants to use
  - (maybe later) we'll eventually add gitea support for users to host their own?
- Initialize a new directory per project with "main" as the default branch
- Author a commit on default branch
  - Default commit message prefilled into the commit message input, user can edit it
  - Can cancel the commit (two buttons, save or cancel)
- Create a new branch
  - name branch
- Author a commit on new branch
- Merge branches into main to accept changes
- Before the user checks out any other branches, we must force them to commit their changes to avoid any conflicts in the underlying binaries.
- After successfully checking out a branch, we need to force the blender file to reopen so that changes are visible.

## Features

- [GUI](./gui.md)
