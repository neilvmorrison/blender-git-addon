# Refactor Skill Agent

## Purpose

Intelligently refactor Python code while preserving behavior, improving readability, and enforcing type safety.

## Input

- `target_file`: Path to Python file to refactor
- `refactoring_goal`: What you want to improve (reduce duplication, add types, etc.)

## Process

1. Analyze code for DRY violations, readability issues, missing types
2. Generate refactored version with rationale
3. Validate with syntax/linting/type checking
4. Present diffs and explanation for review
5. Hoist constants into a constants.py file

## Guidelines

- maximum file length ~300 lines. If exceeded, abstract methods into modules separated by concern

## Output

- Refactored source code
- Change explanation
- Validation results
- Readiness assessment
  i
