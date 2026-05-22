"""Expand ``generate`` blocks at elaboration time."""

from __future__ import annotations

from dataclasses import replace
from typing import Any

from hdl_sim.engine.params import ParameterEvaluator
from hdl_sim.parser.ast import (
    AlwaysBlock,
    BinaryExpr,
    BitSelect,
    Block,
    BlockingAssign,
    CaseItem,
    CaseStmt,
    ConcatExpr,
    ContinuousAssign,
    Declaration,
    Expr,
    ForStmt,
    GenerateBlock,
    GenerateFor,
    GenerateIf,
    IdentRef,
    IfStmt,
    InitialBlock,
    IntLiteral,
    Lvalue,
    Module,
    ModuleInstance,
    NonBlockingAssign,
    PartSelect,
    PortConnection,
    UnaryExpr,
    WhileStmt,
    Stmt,
)


def expand_module_generates(module: Module, param_eval: ParameterEvaluator) -> Module:
    """Return a module with ``generate`` regions unrolled into ordinary items."""

    if not module.generate_blocks:
        return module

    declarations = list(module.declarations)
    continuous = list(module.continuous_assigns)
    initials = list(module.initial_blocks)
    always_blocks = list(module.always_blocks)
    instances = list(module.instances)

    for block in module.generate_blocks:
        for item in block.items:
            _expand_item(
                item,
                param_eval,
                declarations=declarations,
                continuous=continuous,
                initials=initials,
                always_blocks=always_blocks,
                instances=instances,
            )

    return replace(
        module,
        declarations=tuple(declarations),
        continuous_assigns=tuple(continuous),
        initial_blocks=tuple(initials),
        always_blocks=tuple(always_blocks),
        instances=tuple(instances),
        generate_blocks=(),
    )


def _expand_item(
    item: Any,
    param_eval: ParameterEvaluator,
    *,
    declarations: list[Declaration],
    continuous: list[ContinuousAssign],
    initials: list[InitialBlock],
    always_blocks: list[AlwaysBlock],
    instances: list[ModuleInstance],
    name_prefix: str = "",
) -> None:
    if isinstance(item, GenerateFor):
        _expand_generate_for(
            item,
            param_eval,
            declarations=declarations,
            continuous=continuous,
            initials=initials,
            always_blocks=always_blocks,
            instances=instances,
            name_prefix=name_prefix,
        )
        return
    if isinstance(item, GenerateIf):
        _expand_generate_if(
            item,
            param_eval,
            declarations=declarations,
            continuous=continuous,
            initials=initials,
            always_blocks=always_blocks,
            instances=instances,
            name_prefix=name_prefix,
        )
        return
    if isinstance(item, Block):
        for child in item.statements:
            _expand_item(
                child,
                param_eval,
                declarations=declarations,
                continuous=continuous,
                initials=initials,
                always_blocks=always_blocks,
                instances=instances,
                name_prefix=name_prefix,
            )
        return

    expanded = _qualify_item(item, name_prefix)
    if isinstance(expanded, Declaration):
        declarations.append(expanded)
    elif isinstance(expanded, ContinuousAssign):
        continuous.append(expanded)
    elif isinstance(expanded, InitialBlock):
        initials.append(expanded)
    elif isinstance(expanded, AlwaysBlock):
        always_blocks.append(expanded)
    elif isinstance(expanded, ModuleInstance):
        instances.append(expanded)


def _expand_generate_for(
    genfor: GenerateFor,
    param_eval: ParameterEvaluator,
    *,
    declarations: list[Declaration],
    continuous: list[ContinuousAssign],
    initials: list[InitialBlock],
    always_blocks: list[AlwaysBlock],
    instances: list[ModuleInstance],
    name_prefix: str,
) -> None:
    init_value = param_eval.eval(genfor.init)
    step_assign = genfor.step
    if step_assign is None:
        msg = "generate for-loop requires a step assignment"
        raise RuntimeError(msg)

    iteration = 0
    value = init_value
    while param_eval.eval(_substitute_expr(genfor.condition, genfor.genvar, value)):
        if iteration > 1024:
            msg = "generate for-loop iteration limit exceeded"
            raise RuntimeError(msg)
        iteration += 1

        label = genfor.label or "g"
        iter_prefix = f"{name_prefix}{label}_{value}_"

        loop_eval = ParameterEvaluator({**param_eval.snapshot(), genfor.genvar: value})
        body_items = genfor.body if isinstance(genfor.body, tuple) else (genfor.body,)
        for body_item in body_items:
            if isinstance(body_item, Block):
                for stmt in body_item.statements:
                    _expand_item(
                        _substitute_stmt(stmt, genfor.genvar, value),
                        loop_eval,
                        declarations=declarations,
                        continuous=continuous,
                        initials=initials,
                        always_blocks=always_blocks,
                        instances=instances,
                        name_prefix=iter_prefix,
                    )
            else:
                _expand_item(
                    _substitute_any(body_item, genfor.genvar, value),
                    loop_eval,
                    declarations=declarations,
                    continuous=continuous,
                    initials=initials,
                    always_blocks=always_blocks,
                    instances=instances,
                    name_prefix=iter_prefix,
                )

        step_value = loop_eval.eval(_substitute_expr(step_assign.expr, genfor.genvar, value))
        if isinstance(step_assign.target.base, str):
            if step_assign.target.base == genfor.genvar and not step_assign.target.bit:
                value = step_value
            else:
                msg = "generate for step must assign to the genvar"
                raise RuntimeError(msg)
        else:
            msg = "generate for step must assign to the genvar"
            raise RuntimeError(msg)


def _expand_generate_if(
    genif: GenerateIf,
    param_eval: ParameterEvaluator,
    *,
    declarations: list[Declaration],
    continuous: list[ContinuousAssign],
    initials: list[InitialBlock],
    always_blocks: list[AlwaysBlock],
    instances: list[ModuleInstance],
    name_prefix: str,
) -> None:
    branch = genif.then_items if param_eval.eval(genif.condition) else genif.else_items
    for item in branch:
        _expand_item(
            item,
            param_eval,
            declarations=declarations,
            continuous=continuous,
            initials=initials,
            always_blocks=always_blocks,
            instances=instances,
            name_prefix=name_prefix,
        )


def _qualify_item(item: Any, prefix: str) -> Any:
    if not prefix:
        return item
    if isinstance(item, Declaration):
        return replace(item, name=f"{prefix}{item.name}")
    if isinstance(item, ContinuousAssign):
        return replace(item, target=f"{prefix}{item.target}")
    if isinstance(item, ModuleInstance):
        return replace(item, instance_name=f"{prefix}{item.instance_name}")
    return item


def _substitute_any(node: Any, genvar: str, value: int) -> Any:
    from lark import Tree

    if isinstance(node, Tree):
        if node.data == "generate_item" and node.children:
            return _substitute_any(node.children[0], genvar, value)
        return node
    if isinstance(node, Declaration):
        return replace(node, range=_substitute_range(node.range, genvar, value))
    if isinstance(node, Expr):
        return _substitute_expr(node, genvar, value)
    if isinstance(node, Stmt):
        return _substitute_stmt(node, genvar, value)
    if isinstance(node, Block):
        return replace(node, statements=tuple(_substitute_stmt(s, genvar, value) for s in node.statements))
    if isinstance(node, Declaration):
        return replace(node, range=_substitute_range(node.range, genvar, value))
    if isinstance(node, ContinuousAssign):
        return replace(
            node,
            target=node.target,
            expr=_substitute_expr(node.expr, genvar, value),
        )
    if isinstance(node, ModuleInstance):
        return replace(
            node,
            connections=tuple(
                replace(c, expr=_substitute_expr(c.expr, genvar, value)) for c in node.connections
            ),
        )
    return node


def _substitute_range(value_range, genvar: str, value: int):
    if value_range is None:
        return None
    from hdl_sim.parser.ast import ValueRange

    return ValueRange(
        msb=_substitute_expr(value_range.msb, genvar, value),
        lsb=_substitute_expr(value_range.lsb, genvar, value),
    )


def _substitute_stmt(stmt: Any, genvar: str, value: int) -> Any:
    if isinstance(stmt, Block):
        return replace(stmt, statements=tuple(_substitute_stmt(s, genvar, value) for s in stmt.statements))
    if isinstance(stmt, (BlockingAssign, NonBlockingAssign)):
        return replace(
            stmt,
            target=_substitute_lvalue(stmt.target, genvar, value),
            expr=_substitute_expr(stmt.expr, genvar, value),
        )
    if isinstance(stmt, IfStmt):
        return replace(
            stmt,
            condition=_substitute_expr(stmt.condition, genvar, value),
            then_branch=_substitute_stmt(stmt.then_branch, genvar, value) if stmt.then_branch else None,
            else_branch=_substitute_stmt(stmt.else_branch, genvar, value) if stmt.else_branch else None,
        )
    if isinstance(stmt, CaseStmt):
        return replace(
            stmt,
            expression=_substitute_expr(stmt.expression, genvar, value),
            items=tuple(
                replace(
                    item,
                    expressions=tuple(_substitute_expr(e, genvar, value) for e in item.expressions),
                    body=_substitute_stmt(item.body, genvar, value),
                )
                for item in stmt.items
            ),
        )
    if isinstance(stmt, (WhileStmt, ForStmt)):
        return replace(
            stmt,
            condition=_substitute_expr(stmt.condition, genvar, value) if getattr(stmt, "condition", None) else None,
            body=_substitute_stmt(stmt.body, genvar, value),
        )
    if isinstance(stmt, InitialBlock):
        return replace(stmt, body=_substitute_stmt(stmt.body, genvar, value))
    if isinstance(stmt, AlwaysBlock):
        return replace(stmt, body=_substitute_stmt(stmt.body, genvar, value))
    return stmt


def _substitute_lvalue(target: Lvalue, genvar: str, value: int) -> Lvalue:
    return replace(
        target,
        base=target.base,
        bit=_substitute_expr(target.bit, genvar, value) if target.bit is not None else None,
        msb=_substitute_expr(target.msb, genvar, value) if target.msb is not None else None,
        lsb=_substitute_expr(target.lsb, genvar, value) if target.lsb is not None else None,
    )


def _substitute_expr(expr: Expr, genvar: str, value: int) -> Expr:
    if isinstance(expr, IdentRef):
        if expr.name == genvar:
            return IntLiteral(value=value)
        return expr
    if isinstance(expr, IntLiteral):
        return expr
    if isinstance(expr, UnaryExpr):
        return replace(expr, operand=_substitute_expr(expr.operand, genvar, value))
    if isinstance(expr, BinaryExpr):
        return replace(
            expr,
            left=_substitute_expr(expr.left, genvar, value),
            right=_substitute_expr(expr.right, genvar, value),
        )
    if isinstance(expr, BitSelect):
        return replace(
            expr,
            index=_substitute_expr(expr.index, genvar, value),
        )
    if isinstance(expr, PartSelect):
        return replace(
            expr,
            msb=_substitute_expr(expr.msb, genvar, value),
            lsb=_substitute_expr(expr.lsb, genvar, value),
        )
    if isinstance(expr, ConcatExpr):
        return replace(
            expr,
            parts=tuple(_substitute_expr(part, genvar, value) for part in expr.parts),
        )
    return expr
