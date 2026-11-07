# AST Span Replacement with Byte-to-Char Conversion

Status: accepted (generated, pending human review)

## Context

Python 3.8+ AST spans expose byte offsets for line columns, which mismatch string indices when multi-byte UTF-8 characters are present. Mutation testing tools often rewrite whole ASTs via unparse, losing formatting and comments.

## Decision

Extract exact node spans from the source text and convert line-level byte offsets into character indices. Mutate each node independently by splicing `ast.unparse(mutated_node)` into the original source text span.

## Consequences

Maintains comments, surrounding formatting, and multi-byte unicode characters while guaranteeing syntactic correctness of generated mutant source text.
