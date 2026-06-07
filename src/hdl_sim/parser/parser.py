"""Parse a Verilog subset into an AST."""

from __future__ import annotations

from functools import lru_cache
from importlib import resources
from pathlib import Path
import sys
from typing import Any

from lark import Lark, Token, Transformer, Tree, v_args

from hdl_sim.parser.ast import (
    Stmt,
    AlwaysBlock,
    BinaryExpr,
    BitSelect,
    Block,
    BlockingAssign,
    CaseItem,
    CaseStmt,
    ContinuousAssign,
    Declaration,
    DeclKind,
    DelayControl,
    Design,
    EdgeKind,
    EventControl,
    Expr,
    Forever,
    FunctionCall,
    FunctionDef,
    FunctionInput,
    TaskEnable,
    WaitStmt,
    TaskPortKind,
    TaskPort,
    TaskDef,
    IdentDecl,
    IdentRef,
    IfStmt,
    InitialBlock,
    IntLiteral,
    RealLiteral,
    Lvalue,
    Module,
    ModuleInstance,
    NonBlockingAssign,
    PartSelect,
    Port,
    PortConnection,
    PortDirection,
    ParameterDecl,
    ParameterOverride,
    Display,
    DisplayArg,
    StringLiteral,
    SystemTask,
    ValueRange,
    Repeat,
    ForStmt,
    ForkJoin,
    GenerateIf,
    GenerateFor,
    GenerateBlock,
    ConcatExpr,
    ReplicationExpr,
    UnaryExpr,
    WhileStmt,
)
from hdl_sim.parser.preprocess import normalize_source


def _int(token: Token | str | IntLiteral) -> int:
    if isinstance(token, IntLiteral):
        return token.value
    return int(str(token))


def _parse_sized_number(text: str) -> IntLiteral:
    width_text, base_and_digits = text.split("'", 1)
    width = int(width_text.strip())
    base = base_and_digits[0].lower()
    digits = base_and_digits[1:].replace("_", "")
    value = 0
    x_mask = 0
    z_mask = 0

    def consume_binary() -> None:
        nonlocal value, x_mask, z_mask
        for index, char in enumerate(reversed(digits)):
            bit = 1 << index
            lower = char.lower()
            if lower in {"0", "1"}:
                if lower == "1":
                    value |= bit
            elif lower == "x":
                x_mask |= bit
            elif lower == "z":
                z_mask |= bit
                x_mask |= bit
            else:
                msg = f"invalid digit in sized literal: {char}"
                raise ValueError(msg)

    if base == "b":
        consume_binary()
    elif base == "h":
        expanded = ""
        for char in digits:
            lower = char.lower()
            if lower in "0123456789abcdef":
                expanded += f"{int(lower, 16):04b}"
            elif lower == "x":
                expanded += "xxxx"
            elif lower == "z":
                expanded += "zzzz"
            else:
                msg = f"invalid hex digit: {char}"
                raise ValueError(msg)
        digits = expanded
        consume_binary()
    elif base == "d":
        value = int(digits)
    else:
        msg = f"unsupported sized literal base: {base}"
        raise ValueError(msg)
    mask = (1 << width) - 1
    return IntLiteral(value=value & mask, width=width, x_mask=x_mask & mask, z_mask=z_mask & mask)


def _flatten(values: list[Any]) -> list[Any]:
    flattened: list[Any] = []
    for value in values:
        if isinstance(value, list):
            flattened.extend(_flatten(value))
        else:
            flattened.append(value)
    return flattened


def _fold_binary(op: str, children: tuple[Expr, ...]) -> Expr:
    if len(children) == 1:
        return children[0]
    result = children[0]
    for child in children[1:]:
        result = BinaryExpr(op, result, child)
    return result


SelectStep = tuple[str, Expr, Expr | None]


def _lvalue_from_selects(name: str, selects: list[SelectStep]) -> Lvalue:
    if not selects:
        return Lvalue(base=name)
    if len(selects) == 1:
        kind, first, second = selects[0]
        if kind == "part":
            return Lvalue(base=name, msb=first, lsb=second)
        return Lvalue(base=name, bit=first)
    word = selects[0][1]
    kind, first, second = selects[1]
    if kind == "part":
        return Lvalue(base=name, word=word, msb=first, lsb=second)
    return Lvalue(base=name, word=word, bit=first)


def _expr_from_selects(name: str, selects: list[SelectStep]) -> Expr:
    if not selects:
        return IdentRef(name)
    if len(selects) == 1:
        kind, first, second = selects[0]
        if kind == "part":
            return PartSelect(signal=name, msb=first, lsb=second)
        return BitSelect(signal=name, index=first)
    word = selects[0][1]
    kind, first, second = selects[1]
    if kind == "part":
        return PartSelect(signal=name, msb=first, lsb=second, word=word)
    return BitSelect(signal=name, index=first, word=word)


class VerilogTransformer(Transformer):
    def _child_args(self, children: tuple[Any, ...] | list[Any]) -> list[Any]:
        if len(children) == 1 and isinstance(children[0], list):
            return list(children[0])
        return list(children)

    def _resolve_expr(self, value: Any) -> Any:
        if isinstance(value, list):
            if len(value) == 1:
                return self._resolve_expr(value[0])
            if not value:
                msg = "empty expression list"
                raise ValueError(msg)
            msg = "ambiguous expression list"
            raise ValueError(msg)
        if isinstance(value, Tree):
            return self.transform(value)
        return value

    def _normalize_generate_if(self, genif: GenerateIf) -> GenerateIf:
        return GenerateIf(
            condition=genif.condition,
            then_items=tuple(self._resolve_generate_item(i) for i in _flatten(genif.then_items)),
            else_items=tuple(self._resolve_generate_item(i) for i in _flatten(genif.else_items)),
        )

    def _resolve_generate_item(self, item: Any) -> Any:
        if isinstance(item, Tree):
            if item.data == "generate_item" and item.children:
                return self._resolve_generate_item(item.children[0])
            item = self.transform(item)
        if isinstance(item, GenerateIf):
            return self._normalize_generate_if(item)
        if isinstance(item, GenerateFor):
            return GenerateFor(
                genvar=item.genvar,
                init=item.init,
                condition=item.condition,
                step=item.step,
                body=tuple(self._resolve_generate_item(i) for i in _flatten(item.body)),
                label=item.label,
            )
        if isinstance(item, tuple):
            return self._resolve_generate_items(item)
        return item

    def _resolve_generate_items(self, items: Any) -> tuple[Any, ...]:
        if isinstance(items, tuple):
            raw = list(items)
        elif isinstance(items, list):
            raw = items
        else:
            raw = [items]
        resolved: list[Any] = []
        for item in _flatten(raw):
            if isinstance(item, Tree):
                item = self.transform(item)
            if isinstance(item, tuple):
                resolved.extend(item)
            else:
                resolved.append(item)
        return tuple(resolved)

    def design(self, modules: list[Module]) -> Design:
        return Design(modules=tuple(modules))

    def decl_or_stmt(self, item: Any) -> Any:
        return item

    def module(self, items: list[Any]) -> Module:
        name = str(items[0])
        index = 1
        parameters: list[ParameterDecl] = []
        ports: list[Port] = []
        declarations: list[Declaration] = []
        continuous_assigns: list[ContinuousAssign] = []
        initial_blocks: list[InitialBlock] = []
        always_blocks: list[AlwaysBlock] = []
        instances: list[ModuleInstance] = []
        functions: list[FunctionDef] = []
        tasks: list[TaskDef] = []
        generate_blocks: list[GenerateBlock] = []
        if index < len(items) and isinstance(items[index], list) and items[index]:
            if isinstance(items[index][0], ParameterDecl):
                parameters.extend(items[index])
                index += 1
            elif isinstance(items[index][0], Port):
                ports.extend(items[index])
                index += 1
        for item in items[index:]:
            for candidate in _flatten(item if isinstance(item, list) else [item]):
                if isinstance(candidate, Port):
                    ports.append(candidate)
                elif isinstance(candidate, ParameterDecl):
                    parameters.append(candidate)
                elif isinstance(candidate, (Declaration, tuple, ContinuousAssign)):
                    self._distribute_decl_or_assign(declarations, continuous_assigns, candidate)
                elif isinstance(candidate, InitialBlock):
                    initial_blocks.append(candidate)
                elif isinstance(candidate, AlwaysBlock):
                    always_blocks.append(candidate)
                elif isinstance(candidate, FunctionDef):
                    functions.append(candidate)
                elif isinstance(candidate, TaskDef):
                    tasks.append(candidate)
                elif isinstance(candidate, GenerateBlock):
                    generate_blocks.append(candidate)
                elif isinstance(candidate, ModuleInstance):
                    instances.append(candidate)

        return Module(
            name=name,
            parameters=tuple(parameters),
            ports=self._merge_ports(ports),
            declarations=tuple(declarations),
            continuous_assigns=tuple(continuous_assigns),
            initial_blocks=tuple(initial_blocks),
            always_blocks=tuple(always_blocks),
            instances=tuple(instances),
            functions=tuple(functions),
            tasks=tuple(tasks),
            generate_blocks=tuple(generate_blocks),
        )

    def port_list(self, ports: list[Port]) -> list[Port]:
        return ports

    def port(self, items: list[Any]) -> Port:
        return items[0]

    def _merge_ports(self, ports: list[Port]) -> tuple[Port, ...]:
        """Merge ANSI header ports with implicit names and body input/output decls."""
        order: list[str] = []
        by_name: dict[str, Port] = {}
        for port in ports:
            if port.name not in by_name:
                order.append(port.name)
                by_name[port.name] = port
                continue
            prev = by_name[port.name]
            if prev.direction is PortDirection.IMPLICIT and port.direction is not PortDirection.IMPLICIT:
                by_name[port.name] = port
            elif port.direction is not PortDirection.IMPLICIT and prev.direction is PortDirection.IMPLICIT:
                by_name[port.name] = port
            elif port.direction is not PortDirection.IMPLICIT and prev.direction is not PortDirection.IMPLICIT:
                if prev.direction != port.direction or prev.range != port.range:
                    msg = f"conflicting port declaration for {port.name}"
                    raise ValueError(msg)
        merged = [by_name[n] for n in order]
        unresolved = [p.name for p in merged if p.direction is PortDirection.IMPLICIT]
        if unresolved:
            msg = f"port direction missing for: {', '.join(unresolved)}"
            raise ValueError(msg)
        return tuple(merged)

    @v_args(inline=True)
    def port_name(self, name: Token) -> Port:
        return Port(direction=PortDirection.IMPLICIT, name=str(name))

    @v_args(inline=True)
    def port_type(self, kind: Token) -> Token:
        return kind

    def _port_net_kind(self, value: Any) -> DeclKind | None:
        if isinstance(value, Tree) and str(value.data) == "port_type" and value.children:
            value = value.children[0]
        if isinstance(value, Token):
            text = str(value).lower()
        elif isinstance(value, str):
            text = value.lower()
        else:
            return None
        if text == "wire":
            return DeclKind.WIRE
        if text == "reg":
            return DeclKind.REG
        return None

    def _port_decl_with_dir(self, port_dir: PortDirection, *rest: Any) -> Port:
        rest_list = [r for r in rest if not isinstance(r, Token) or str(r.type) != "SIGNED"]
        is_signed = any(isinstance(r, Token) and str(r.type) == "SIGNED" for r in rest)
        net_kind = None
        if rest_list and self._port_net_kind(rest_list[0]) is not None:
            net_kind = self._port_net_kind(rest_list[0])
            rest_list = rest_list[1:]
        if rest_list and rest_list[0] is True:
            is_signed = True
            rest_list = rest_list[1:]
        if len(rest_list) == 2:
            value_range, name = rest_list
            return Port(
                direction=port_dir,
                name=str(name),
                range=value_range,
                net_kind=net_kind,
                is_signed=is_signed,
            )
        (name,) = rest_list
        return Port(direction=port_dir, name=str(name), net_kind=net_kind, is_signed=is_signed)

    def port_decls_body(self, items: list[Any]) -> list[Port]:
        dir_text = str(items[0]).lower()
        if dir_text == "input":
            port_dir = PortDirection.INPUT
        elif dir_text == "inout":
            port_dir = PortDirection.INOUT
        else:
            port_dir = PortDirection.OUTPUT
        idx = 1
        net_kind = None
        if idx < len(items) and self._port_net_kind(items[idx]) is not None:
            net_kind = self._port_net_kind(items[idx])
            idx += 1
        is_signed = False
        if idx < len(items) and items[idx] is True:
            is_signed = True
            idx += 1
        value_range = None
        if idx < len(items) and not isinstance(items[idx], list):
            value_range = items[idx]
            idx += 1
        names = items[idx]
        return [
            Port(
                direction=port_dir,
                name=str(name),
                range=value_range,
                net_kind=net_kind,
                is_signed=is_signed,
            )
            for name in names
        ]

    @v_args(inline=True)
    def port_decl(self, direction: Token, *rest: Any) -> Port:
        dir_text = str(direction).lower()
        if dir_text == "input":
            port_dir = PortDirection.INPUT
        elif dir_text == "inout":
            port_dir = PortDirection.INOUT
        else:
            port_dir = PortDirection.OUTPUT
        return self._port_decl_with_dir(port_dir, *rest)

    @v_args(inline=True)
    def module_instance(
        self,
        module_type: Token,
        *rest: Any,
    ) -> ModuleInstance:
        overrides: tuple[ParameterOverride, ...] = ()
        instance_name: Token
        connections: list[PortConnection] | None = None
        if len(rest) == 1:
            (instance_name,) = rest
        elif len(rest) == 2:
            first, second = rest
            if isinstance(first, list):
                overrides = tuple(first)
                instance_name = second
            else:
                instance_name, connections = first, second
        elif len(rest) == 3:
            overrides = tuple(rest[0])
            instance_name, connections = rest[1], rest[2]
        else:
            msg = "invalid module instance"
            raise ValueError(msg)
        return ModuleInstance(
            module_type=str(module_type),
            instance_name=str(instance_name),
            parameter_overrides=overrides,
            connections=tuple(connections or []),
        )

    def parameter_list(self, params: list[ParameterDecl]) -> list[ParameterDecl]:
        return params

    def parameter_assign(self, items: list[Any]) -> ParameterDecl:
        return self.parameter_body(items)

    def parameter_decl(self, body: ParameterDecl) -> ParameterDecl:
        return body

    def parameter_body(self, items: list[Any]) -> ParameterDecl:
        expr = items[-1]
        name = items[-2]
        if not isinstance(name, Token):
            raise TypeError(f"expected parameter name token, got {type(name)!r}")
        if not isinstance(expr, Expr):
            raise TypeError(f"expected parameter expr, got {type(expr)!r}")
        return ParameterDecl(name=str(name), expr=expr)

    def parameter_decl_stmt_multi(self, items: list[Any]) -> list[ParameterDecl]:
        return [item for item in items if isinstance(item, ParameterDecl)]

    @v_args(inline=True)
    def parameter_decl_stmt(self, name: Token, expr: Expr) -> ParameterDecl:
        return ParameterDecl(name=str(name), expr=expr)

    def param_instance(self, overrides: list[ParameterOverride]) -> list[ParameterOverride]:
        return overrides

    @v_args(inline=True)
    def param_override(self, name: Token, expr: Expr) -> ParameterOverride:
        return ParameterOverride(name=str(name), expr=expr)

    def port_connections(self, connections: list[PortConnection]) -> list[PortConnection]:
        return connections

    @v_args(inline=True)
    @v_args(inline=True)
    def named_port_connection(self, port: Token, expr: Expr) -> PortConnection:
        return PortConnection(port=str(port), expr=expr)

    @v_args(inline=True)
    def positional_port_connection(self, expr: Expr) -> PortConnection:
        return PortConnection(port="", expr=expr)

    def _distribute_decl_or_assign(
        self,
        declarations: list[Declaration],
        continuous_assigns: list[ContinuousAssign] | None,
        item: Any,
    ) -> None:
        for candidate in _flatten(item if isinstance(item, list) else [item]):
            if isinstance(candidate, Declaration):
                declarations.append(candidate)
            elif isinstance(candidate, tuple):
                for sub in candidate:
                    if isinstance(sub, Declaration):
                        declarations.append(sub)
                    elif isinstance(sub, ContinuousAssign):
                        if continuous_assigns is not None:
                            continuous_assigns.append(sub)
            elif isinstance(candidate, ContinuousAssign):
                if continuous_assigns is not None:
                    continuous_assigns.append(candidate)

    @v_args(inline=True)
    def ident_list(self, first: Token, *rest: Token) -> list[str]:
        return [str(first), *(str(r) for r in rest)]

    def ident_decl_list(self, items: list[IdentDecl]) -> list[IdentDecl]:
        return items

    @v_args(inline=True)
    def ident_decl(self, name: Token, unpacked: ValueRange | None = None) -> IdentDecl:
        return IdentDecl(name=str(name), unpacked_range=unpacked)

    @v_args(inline=True)
    def unpacked_dimension(self, msb: Expr, lsb: Expr) -> ValueRange:
        return ValueRange(msb=msb, lsb=lsb)

    @v_args(inline=True)
    def signed_opt(self, _signed: Token | None = None) -> bool:
        return _signed is not None

    def _parse_decl_head(self, children: list[Any]) -> tuple[bool, ValueRange | None, Any]:
        filtered = [
            c
            for c in children
            if not isinstance(c, Token) or str(c.type) not in {"REG", "WIRE", "INTEGER", "REAL"}
        ]
        is_signed = False
        idx = 0
        if idx < len(filtered) and filtered[idx] is True:
            is_signed = True
            idx += 1
        range_node = None
        if idx < len(filtered) and isinstance(filtered[idx], ValueRange):
            range_node = filtered[idx]
            idx += 1
        rest = filtered[idx:]
        return is_signed, range_node, rest[0] if rest else None

    def _decls_from_ident_decls(
        self,
        kind: DeclKind,
        ident_decls: list[IdentDecl],
        range_node: ValueRange | None,
        *,
        is_signed: bool = False,
    ) -> tuple[Declaration, ...]:
        decls: list[Declaration] = []
        for item in ident_decls:
            decls.append(
                Declaration(
                    kind=kind,
                    name=item.name,
                    range=range_node,
                    unpacked_range=item.unpacked_range,
                    is_signed=is_signed,
                )
            )
        return tuple(decls)

    def _decls_from_names(
        self,
        kind: DeclKind,
        names: list[str],
        range_node: ValueRange | None = None,
        *,
        is_signed: bool = False,
    ) -> tuple[Declaration, ...]:
        return self._decls_from_ident_decls(
            kind,
            [IdentDecl(name=name) for name in names],
            range_node,
            is_signed=is_signed,
        )

    def _multi_decl(self, kind: DeclKind, children: list[Any]) -> tuple[Declaration, ...]:
        is_signed, range_node, payload = self._parse_decl_head(children)
        if kind is DeclKind.INTEGER:
            is_signed = True
        if payload is None:
            return ()
        if isinstance(payload, list) and payload and isinstance(payload[0], IdentDecl):
            return self._decls_from_ident_decls(kind, payload, range_node, is_signed=is_signed)
        if isinstance(payload, list):
            return self._decls_from_names(kind, payload, range_node, is_signed=is_signed)
        return ()

    def make_reg_decls(self, children: list[Any]) -> tuple[Declaration, ...]:
        return self._multi_decl(DeclKind.REG, children)

    def make_wire_decls(self, children: list[Any]) -> tuple[Declaration, ...]:
        return self._multi_decl(DeclKind.WIRE, children)

    def make_integer_decls(self, children: list[Any]) -> tuple[Declaration, ...]:
        return self._multi_decl(DeclKind.INTEGER, children)

    def make_real_decls(self, children: list[Any]) -> tuple[Declaration, ...]:
        return self._multi_decl(DeclKind.REAL, children)

    def _decl_assign(self, kind: DeclKind, children: list[Any]) -> tuple[Declaration, ContinuousAssign]:
        is_signed, range_node, rest = self._parse_decl_head(children)
        if not rest:
            msg = "invalid declaration with assignment"
            raise ValueError(msg)
        if isinstance(rest, list) and len(rest) >= 2:
            name, expr = rest[0], rest[1]
        else:
            name, expr = rest, children[-1]
        decl = Declaration(
            kind=kind,
            name=str(name),
            range=range_node,
            is_signed=is_signed,
        )
        return (decl, ContinuousAssign(target=str(name), expr=expr))

    def make_reg_decl_assign(self, children: list[Any]) -> tuple[Declaration, ContinuousAssign]:
        return self._decl_assign(DeclKind.REG, children)

    def make_wire_decl_assign(self, children: list[Any]) -> tuple[Declaration, ContinuousAssign]:
        return self._decl_assign(DeclKind.WIRE, children)

    def make_integer_decl_assign(self, children: list[Any]) -> tuple[Declaration, ContinuousAssign]:
        return self._decl_assign(DeclKind.INTEGER, children)

    @v_args(inline=True)
    def declaration(self, *rest: Any) -> Declaration | tuple[Declaration, ...]:
        """Legacy fallback if a single declaration slips through."""
        if len(rest) == 1 and isinstance(rest[0], tuple):
            return rest[0]
        if len(rest) == 3:
            decl_type, range_node, name = rest
            if isinstance(decl_type, Token) and str(decl_type.type) == "REG":
                kind = DeclKind.REG
            elif isinstance(decl_type, Token) and str(decl_type.type) == "INTEGER":
                kind = DeclKind.INTEGER
            else:
                kind = DeclKind.WIRE
            return Declaration(kind=kind, name=str(name), range=range_node)
        decl_type, name = rest
        if isinstance(decl_type, Token) and str(decl_type.type) == "REG":
            kind = DeclKind.REG
        elif isinstance(decl_type, Token) and str(decl_type.type) == "INTEGER":
            kind = DeclKind.INTEGER
        else:
            kind = DeclKind.WIRE
        return Declaration(kind=kind, name=str(name))

    @v_args(inline=True)
    def range(self, msb: Expr, lsb: Expr) -> ValueRange:
        return ValueRange(msb=msb, lsb=lsb)

    def continuous_assign(self, items: list[Any]) -> ContinuousAssign:
        filtered = [item for item in items if not isinstance(item, Token)]
        target, expr = filtered[0], filtered[1]
        return ContinuousAssign(target=target.base, expr=expr)

    def initial_block(self, items: list[Any]) -> InitialBlock:
        body = items[-1]
        return InitialBlock(body=body)

    def always_block(self, items: list[Any]) -> AlwaysBlock:
        return AlwaysBlock(sensitivity=items[-2], body=items[-1])

    def always_delay(self, items: list[Any]) -> AlwaysBlock:
        return AlwaysBlock(sensitivity=(), body=Forever(items[-1]))

    def always_plain(self, items: list[Any]) -> AlwaysBlock:
        return AlwaysBlock(sensitivity=(), body=Forever(items[-1]))

    @v_args(inline=True)
    def posedge(self, name: Token) -> tuple[EdgeKind, str]:
        return (EdgeKind.POSEDGE, str(name))

    @v_args(inline=True)
    def negedge(self, name: Token) -> tuple[EdgeKind, str]:
        return (EdgeKind.NEGEDGE, str(name))

    @v_args(inline=True)
    def level(self, name: Token) -> tuple[None, str]:
        return (None, str(name))

    def _collect_sensitivity_edges(self, items: list[Any]) -> tuple[tuple[EdgeKind | None, str], ...]:
        edges: list[tuple[EdgeKind | None, str]] = []

        def walk(value: Any) -> None:
            if isinstance(value, tuple):
                if len(value) == 2 and isinstance(value[0], EdgeKind):
                    edges.append(value)
                    return
                for part in value:
                    walk(part)
            elif isinstance(value, list):
                for part in value:
                    walk(part)

        walk(items)
        return tuple(edges)

    def sensitivity_list(self, items: list[Any]) -> tuple[tuple[EdgeKind | None, str], ...]:
        return self._collect_sensitivity_edges(items)

    def sensitivity(self, items: list[Any]) -> tuple[tuple[EdgeKind | None, str], ...] | None:
        flat = _flatten(items if isinstance(items, list) else [items])
        if len(flat) == 1 and str(flat[0]) == "*":
            return None
        return self._collect_sensitivity_edges(flat)

    def begin_labeled(self, items: list[Any]) -> Block:
        label = str(items[2])
        stmt_list = items[3]
        return Block(statements=tuple(_flatten(stmt_list)), label=label)

    def begin_plain(self, items: list[Any]) -> Block:
        for item in items:
            if isinstance(item, list):
                return Block(statements=tuple(_flatten(item)))
        return Block(statements=tuple(_flatten(items[-1])))

    def begin_end_block(self, stmt_list: list[Stmt]) -> Block:
        return Block(statements=tuple(_flatten(stmt_list)))

    def stmt_list(self, stmts: list[Stmt]) -> list[Stmt]:
        return stmts

    def display_args(self, args: list[DisplayArg]) -> list[DisplayArg]:
        return args

    def display_arg(self, items: list[Any]) -> DisplayArg:
        value = items[0] if isinstance(items, list) else items
        if isinstance(value, Tree) and str(value.data) == "string_expr" and value.children:
            value = value.children[0]
        if isinstance(value, StringLiteral):
            return DisplayArg(text=value.value)
        return DisplayArg(expr=value)

    @v_args(inline=True)
    def display(self, args: list[DisplayArg] | None = None) -> Display:
        return Display(args=tuple(args or []))

    @v_args(inline=True)
    def finish(self) -> SystemTask:
        return SystemTask(name="finish")

    @v_args(inline=True)
    def stop(self) -> SystemTask:
        return SystemTask(name="stop")

    @v_args(inline=True)
    def dumpfile(self, path: StringLiteral) -> SystemTask:
        return SystemTask(name="dumpfile", args=(DisplayArg(text=path.value),))

    @v_args(inline=True)
    def dumpvars(self, args: list[DisplayArg] | None = None) -> SystemTask:
        return SystemTask(name="dumpvars", args=tuple(args or []))

    @v_args(inline=True)
    def STRING(self, token: Token) -> StringLiteral:
        raw = str(token)
        return StringLiteral(value=raw[1:-1])

    @v_args(inline=True)
    def string_expr(self, lit: StringLiteral) -> StringLiteral:
        return lit

    def signal_ref(self, children: list[Any]) -> tuple[str, list[SelectStep]]:
        args = self._child_args(children)
        name = str(args[0])
        selects = [item for item in args[1:] if isinstance(item, tuple)]
        return (name, selects)

    @v_args(inline=True)
    def to_lvalue(self, ref: tuple[str, list[SelectStep]]) -> Lvalue:
        return _lvalue_from_selects(ref[0], ref[1])

    @v_args(inline=True)
    def signal_expr(self, ref: tuple[str, list[SelectStep]]) -> Expr:
        return _expr_from_selects(ref[0], ref[1])

    @v_args(inline=True)
    def hier_ident(self, first: Token, *rest: Token) -> IdentRef:
        parts = [str(first)] + [str(r) for r in rest]
        return IdentRef(name=".".join(parts))

    @v_args(inline=True)
    def sys_ident(self, token: Token) -> IdentRef:
        return IdentRef(name=str(token))

    @v_args(inline=True)
    def bit_sel(self, index: Expr) -> SelectStep:
        return ("bit", index, None)

    @v_args(inline=True)
    def part_sel(self, msb: Expr, lsb: Expr) -> SelectStep:
        return ("part", msb, lsb)

    @v_args(inline=True)
    def signed_cast(self, operand: Expr) -> UnaryExpr:
        return UnaryExpr(op="$signed", operand=operand)

    @v_args(inline=True)
    def unsigned_cast(self, operand: Expr) -> UnaryExpr:
        return UnaryExpr(op="$unsigned", operand=operand)

    @v_args(inline=True)
    def blocking_assign(self, target: Lvalue, expr: Any) -> BlockingAssign:
        return BlockingAssign(target=target, expr=self._resolve_expr(expr))

    @v_args(inline=True)
    def nonblocking_assign(self, target: Lvalue, expr: Any) -> NonBlockingAssign:
        return NonBlockingAssign(target=target, expr=self._resolve_expr(expr))

    @v_args(inline=True)
    def empty_stmt(self) -> Block:
        return Block(statements=())

    @v_args(inline=True)
    def delay_control(self, delay: Expr, body: Stmt) -> DelayControl:
        return DelayControl(delay=delay, body=body)

    @v_args(inline=True)
    def forever_stmt(self, body: Stmt) -> Forever:
        return Forever(body=body)

    @v_args(inline=True)
    def repeat_stmt(self, count: Token | IntLiteral, body: Stmt) -> Repeat:
        value = count.value if isinstance(count, IntLiteral) else _int(count)
        return Repeat(count=value, body=body)



    def generate_block(self, items: list[Any]) -> GenerateBlock:
        return GenerateBlock(items=tuple(self._resolve_generate_item(i) for i in _flatten(items)))

    def _flatten_body_items(self, items: Any) -> tuple[Any, ...]:
        flat: list[Any] = []
        for item in _flatten(items if isinstance(items, (list, tuple)) else [items]):
            resolved = self._resolve_generate_item(item)
            if isinstance(resolved, Declaration):
                flat.append(resolved)
            elif isinstance(resolved, tuple):
                for sub in resolved:
                    if isinstance(sub, Declaration):
                        flat.append(sub)
                    else:
                        flat.append(sub)
            elif resolved is not None:
                flat.append(resolved)
        return tuple(flat)

    def _strip_begin_tokens(self, items: list[Any]) -> list[Any]:
        return [
            item
            for item in items
            if not (isinstance(item, Token) and str(item).lower() == "begin")
        ]

    @v_args(inline=True)
    def gen_begin_labeled(self, *items: Any) -> tuple[str, Any]:
        cleaned = self._strip_begin_tokens(list(items))
        if not cleaned:
            return ("labeled", "gen", ())
        label = cleaned[0]
        body = self._flatten_body_items(cleaned[1:])
        return ("labeled", str(label), body)

    def gen_begin(self, items: list[Any]) -> tuple[Any, ...]:
        return self._flatten_body_items(self._strip_begin_tokens(items))

    def gen_single(self, item: Any) -> tuple[Any, ...]:
        return self._flatten_body_items([item])

    @v_args(inline=True)
    def genvar_init(self, *items: Any) -> tuple[str, Expr]:
        if len(items) == 3:
            return str(items[1]), items[2]
        return str(items[0]), items[1]

    def gen_for(self, *children: Any) -> GenerateFor:
        flat = self._child_args(children)
        genvar, init = flat[0]
        condition = flat[1]
        step = flat[2]
        body_raw = flat[3]
        label = None
        if isinstance(body_raw, tuple) and len(body_raw) == 3 and body_raw[0] == "labeled":
            label = body_raw[1]
            body = body_raw[2] if isinstance(body_raw[2], tuple) else (body_raw[2],)
        else:
            body = self._resolve_generate_items(body_raw)
        return GenerateFor(
            genvar=genvar,
            init=init,
            condition=condition,
            step=step,
            body=body,
            label=label,
        )

    def gen_if(self, *children: Any) -> GenerateIf:
        flat = self._child_args(children)
        condition = flat[0]
        then_items = self._resolve_generate_items(flat[1])
        else_items: tuple[Any, ...] = ()
        if len(flat) > 2:
            else_items = self._resolve_generate_items(flat[2])
        return self._normalize_generate_if(GenerateIf(condition=condition, then_items=then_items, else_items=else_items))

    def _fork_body(self, items: list[Any]) -> Stmt:
        candidate = items[0] if len(items) == 1 else items
        if isinstance(candidate, Block):
            return candidate
        if isinstance(candidate, list):
            return Block(statements=tuple(s for s in _flatten(candidate) if isinstance(s, Stmt)))
        if isinstance(candidate, tuple):
            return Block(statements=tuple(s for s in _flatten(list(candidate)) if isinstance(s, Stmt)))
        return candidate if isinstance(candidate, Stmt) else Block(statements=())

    def fork_join(self, items: list[Any]) -> ForkJoin:
        return ForkJoin(body=self._fork_body(items), join_mode="join")

    def fork_join_any(self, items: list[Any]) -> ForkJoin:
        return ForkJoin(body=self._fork_body(items), join_mode="join_any")

    def fork_join_none(self, items: list[Any]) -> ForkJoin:
        return ForkJoin(body=self._fork_body(items), join_mode="join_none")


    def task_decl(self, children: list[Any]) -> TaskDef:
        flat = self._child_args(tuple(children))
        name = str(flat[0])
        ports: list[TaskPort] = []
        declarations: list[Declaration] = []
        statements: list[Stmt] = []
        for item in flat[1:]:
            if isinstance(item, TaskPort):
                ports.append(item)
            elif isinstance(item, (Declaration, tuple, ContinuousAssign)):
                self._distribute_decl_or_assign(declarations, None, item)
            elif isinstance(item, Block):
                statements.extend(item.statements)
            elif isinstance(item, Stmt):
                statements.append(item)
            elif hasattr(item, "data") and item.data == "task_item":
                resolved = self.transform(item)
                if isinstance(resolved, Block):
                    statements.extend(resolved.statements)
                elif isinstance(resolved, Stmt):
                    statements.append(resolved)
        return TaskDef(
            name=name,
            ports=tuple(ports),
            declarations=tuple(declarations),
            body_statements=tuple(statements),
        )

    def task_item(self, children: list[Any]) -> Stmt | Block:
        return self._resolve_expr(children[0])

    @v_args(inline=True)
    def task_input(self, *rest: Any) -> TaskPort:
        if len(rest) == 2:
            value_range, name = rest
            return TaskPort(kind=TaskPortKind.INPUT, name=str(name), range=value_range)
        (name,) = rest
        return TaskPort(kind=TaskPortKind.INPUT, name=str(name))

    @v_args(inline=True)
    def task_output(self, *rest: Any) -> TaskPort:
        if len(rest) == 2:
            value_range, name = rest
            return TaskPort(kind=TaskPortKind.OUTPUT, name=str(name), range=value_range)
        (name,) = rest
        return TaskPort(kind=TaskPortKind.OUTPUT, name=str(name))

    def wait_stmt(self, items: list[Any]) -> WaitStmt:
        condition = items[-1]
        return WaitStmt(condition=condition)

    @v_args(inline=True)
    def task_call(self, name: Token, *args: Expr) -> TaskEnable:
        return TaskEnable(name=str(name), args=tuple(args))

    @v_args(inline=True)
    def task_call_empty(self, name: Token) -> TaskEnable:
        return TaskEnable(name=str(name), args=())


    def function_decl(self, children: list[Any]) -> FunctionDef:
        flat = self._child_args(tuple(children))
        index = 0
        return_range: ValueRange | None = None
        if index < len(flat) and isinstance(flat[index], ValueRange):
            return_range = flat[index]
            index += 1
        name = str(flat[index])
        index += 1
        inputs: list[FunctionInput] = []
        declarations: list[Declaration] = []
        statements: list[Stmt] = []
        for item in flat[index:]:
            if isinstance(item, FunctionInput):
                inputs.append(item)
            elif isinstance(item, (Declaration, tuple, ContinuousAssign)):
                self._distribute_decl_or_assign(declarations, None, item)
            elif isinstance(item, Block):
                statements.extend(item.statements)
            elif isinstance(item, Stmt):
                statements.append(item)
            elif hasattr(item, 'data') and item.data == 'function_item':
                resolved = self.transform(item)
                if isinstance(resolved, Block):
                    statements.extend(resolved.statements)
                elif isinstance(resolved, Stmt):
                    statements.append(resolved)
        return FunctionDef(
            name=name,
            return_range=return_range,
            inputs=tuple(inputs),
            declarations=tuple(declarations),
            body_statements=tuple(statements),
        )

    def function_item(self, children: list[Any]) -> Stmt | Block:
        return self._resolve_expr(children[0])

    @v_args(inline=True)
    def func_input(self, *rest: Any) -> FunctionInput:
        if len(rest) == 2:
            value_range, name = rest
            return FunctionInput(name=str(name), range=value_range)
        (name,) = rest
        return FunctionInput(name=str(name))

    @v_args(inline=True)
    def func_call(self, name: Token, *args: Expr) -> FunctionCall:
        return FunctionCall(name=str(name), args=tuple(args))

    def concat_expr(self, body: Expr) -> Expr:
        return body

    def concat_single(self, value: Any) -> ConcatExpr:
        expr = self._resolve_expr(value)
        return ConcatExpr(parts=(expr,))

    def concat_list(self, *exprs: Any) -> ConcatExpr:
        flat = self._child_args(exprs)
        return ConcatExpr(parts=tuple(self._resolve_expr(e) for e in flat))

    @v_args(inline=True)
    def replication(self, count: Expr, inner: Expr) -> ReplicationExpr:
        return ReplicationExpr(count=count, expr=inner)

    @v_args(inline=True)
    def for_init(self, target: Lvalue, expr: Expr) -> BlockingAssign:
        return BlockingAssign(target=target, expr=expr)

    @v_args(inline=True)
    def for_step(self, target: Lvalue, expr: Expr) -> BlockingAssign:
        return BlockingAssign(target=target, expr=expr)

    def for_stmt(self, children: list[Any]) -> ForStmt:
        flat = self._child_args(tuple(children))
        init: BlockingAssign | None = None
        condition: Expr | None = None
        step: BlockingAssign | None = None
        body: Stmt = flat[-1]
        index = 0
        if index < len(flat) - 1 and isinstance(flat[index], BlockingAssign):
            init = flat[index]
            index += 1
        if index < len(flat) - 1 and not isinstance(flat[index], BlockingAssign):
            condition = flat[index]
            index += 1
        if index < len(flat) - 1 and isinstance(flat[index], BlockingAssign):
            step = flat[index]
        return ForStmt(init=init, condition=condition, step=step, body=body)

    @v_args(inline=True)
    def monitor(self, args: list[DisplayArg] | None = None) -> SystemTask:
        return SystemTask(name="monitor", args=tuple(args or []))

    @v_args(inline=True)
    def generic_system_task(self, name: Token, args: list[DisplayArg] | None = None) -> SystemTask:
        return SystemTask(name=str(name).lstrip("$"), args=tuple(args or []))
    @v_args(inline=True)
    def while_stmt(self, condition: Expr, body: Stmt) -> WhileStmt:
        return WhileStmt(condition=condition, body=body)

    @v_args(inline=True)
    def if_stmt(self, condition: Expr, then_branch: Stmt, else_branch: Stmt | None = None) -> IfStmt:
        return IfStmt(condition=condition, then_branch=then_branch, else_branch=else_branch)

    def case(self, children: list[Any]) -> CaseStmt:
        flat = self._child_args(tuple(children))
        return CaseStmt(expression=flat[0], items=tuple(flat[1:]), case_style="case")

    def casex(self, children: list[Any]) -> CaseStmt:
        flat = self._child_args(tuple(children))
        return CaseStmt(expression=flat[0], items=tuple(flat[1:]), case_style="casex")

    def casez(self, children: list[Any]) -> CaseStmt:
        flat = self._child_args(tuple(children))
        return CaseStmt(expression=flat[0], items=tuple(flat[1:]), case_style="casez")

    @v_args(inline=True)
    def case_item(self, pattern: Any, body: Stmt) -> CaseItem:
        if pattern == "default":
            return CaseItem(expressions=(), body=body)
        if isinstance(pattern, tuple):
            return CaseItem(expressions=pattern, body=body)
        return CaseItem(expressions=(pattern,), body=body)

    @v_args(inline=True)
    def default_pat(self) -> str:
        return "default"

    def expr_pat(self, children: list[Any]) -> tuple[Expr, ...]:
        return tuple(self._child_args(tuple(children)))

    @v_args(inline=True)
    def ev_posedge(self, name: Token) -> Expr:
        return UnaryExpr("posedge", IdentRef(str(name)))

    @v_args(inline=True)
    def ev_negedge(self, name: Token) -> Expr:
        return UnaryExpr("negedge", IdentRef(str(name)))

    @v_args(inline=True)
    def ev_expr(self, expr: Expr) -> Expr:
        return expr

    @v_args(inline=True)
    def event_control(self, *children: Any) -> EventControl:
        body = children[-1]
        if isinstance(body, Tree):
            body = self.transform(body)
        events = tuple(children[:-1])
        return EventControl(events=events, body=body)

    def ternary_expr(self, *children: Any) -> Expr:
        children = self._child_args(children)
        if len(children) == 1:
            return children[0]
        condition, true_expr, false_expr = children
        return BinaryExpr("?:", condition, BinaryExpr("?:", true_expr, false_expr))

    def lor_expr(self, children: list[Any]) -> Expr:
        resolved = [self._resolve_expr(c) for c in children]
        return _fold_binary("||", tuple(resolved))

    def land_expr(self, children: list[Any]) -> Expr:
        resolved = [self._resolve_expr(c) for c in children]
        return _fold_binary("&&", tuple(resolved))

    def bitor_expr(self, children: list[Any]) -> Expr:
        resolved = [self._resolve_expr(c) for c in children]
        return _fold_binary("|", tuple(resolved))

    def bitxor_expr(self, children: list[Any]) -> Expr:
        resolved = [self._resolve_expr(c) for c in children]
        return _fold_binary("^", tuple(resolved))

    def bitand_expr(self, children: list[Any]) -> Expr:
        resolved = [self._resolve_expr(c) for c in children]
        return _fold_binary("&", tuple(resolved))

    def eq_expr(self, *children: Any) -> Expr:
        children = self._child_args(children)
        resolved = [self._resolve_expr(child) for child in children]
        if len(resolved) == 1:
            return resolved[0]
        if len(resolved) == 2:
            return BinaryExpr("==", resolved[0], resolved[1])
        result = resolved[0]
        index = 1
        while index < len(resolved):
            op = str(resolved[index])
            if op in {"!=", "=="}:
                result = BinaryExpr(op, result, resolved[index + 1])
                index += 2
                continue
            right = resolved[index + 1]
            result = BinaryExpr(op, result, right)
            index += 2
        return result

    def rel_expr(self, *children: Any) -> Expr:
        children = self._child_args(children)
        resolved = [self._resolve_expr(child) for child in children]
        if len(resolved) == 1:
            return resolved[0]
        result = resolved[0]
        index = 1
        while index < len(resolved):
            op = str(resolved[index])
            if op in {"ADD_OP", "+"}:
                op = "+"
            elif op in {"SUB_OP", "-"}:
                op = "-"
            elif op.startswith("OP_"):
                op = op[3:].lower()
                if op == "lt":
                    op = "<"
                elif op == "le":
                    op = "<="
                elif op == "gt":
                    op = ">"
                elif op == "ge":
                    op = ">="
            right = resolved[index + 1]
            result = BinaryExpr(op, result, right)
            index += 2
        return result

    def shift_expr(self, *children: Any) -> Expr:
        children = self._child_args(children)
        resolved = [self._resolve_expr(child) for child in children]
        if len(resolved) == 1:
            return resolved[0]
        result = resolved[0]
        index =  1
        while index < len(resolved):
            op = str(resolved[index])
            if op.startswith("OP_"):
                if "ASHR" in op:
                    op = ">>>"
                elif "SHL" in op:
                    op = "<<"
                else:
                    op = ">>"
            right = resolved[index + 1]
            result = BinaryExpr(op, result, right)
            index += 2
        return result

    def add_expr(self, children: list[Any]) -> Expr:
        if len(children) == 1 and isinstance(children[0], list):
            children = children[0]
        if len(children) == 1:
            return children[0]
        if len(children) >= 3 and all(not isinstance(child, Token) for child in children):
            return _fold_binary("+", tuple(children))
        result = children[0]
        index = 1
        while index < len(children):
            op = str(children[index])
            right = children[index + 1]
            result = BinaryExpr(op, result, right)
            index += 2
        return result

    def mul_expr(self, *children: Any) -> Expr:
        return self.add_expr(list(children))

    @v_args(inline=True)
    def not_(self, operand: Expr) -> UnaryExpr:
        return UnaryExpr("!", operand)

    @v_args(inline=True)
    def invert(self, operand: Expr) -> UnaryExpr:
        return UnaryExpr("~", operand)

    @v_args(inline=True)
    def neg(self, operand: Expr) -> UnaryExpr:
        return UnaryExpr("-", operand)

    @v_args(inline=True)
    def uand(self, operand: Expr) -> UnaryExpr:
        return UnaryExpr("uand", operand)

    @v_args(inline=True)
    def uor(self, operand: Expr) -> UnaryExpr:
        return UnaryExpr("uor", operand)

    @v_args(inline=True)
    def uxor(self, operand: Expr) -> UnaryExpr:
        return UnaryExpr("uxor", operand)

    @v_args(inline=True)
    def NUMBER(self, token: Token) -> IntLiteral:
        return IntLiteral(value=_int(token))

    @v_args(inline=True)
    def REAL_NUMBER(self, token: Token) -> RealLiteral:
        return RealLiteral(value=float(str(token)))

    @v_args(inline=True)
    def sized_number(self, token: Token) -> IntLiteral:
        return _parse_sized_number(str(token))


@lru_cache(maxsize=1)
def _grammar_text() -> str:
    try:
        return resources.files("hdl_sim.parser").joinpath("verilog.lark").read_text(encoding="utf-8")
    except (FileNotFoundError, OSError, TypeError):
        pass

    candidates: list[Path] = []
    if getattr(sys, "frozen", False):
        meipass = Path(getattr(sys, "_MEIPASS", ""))
        candidates.append(meipass / "hdl_sim" / "parser" / "verilog.lark")
    candidates.append(Path(__file__).resolve().parent / "verilog.lark")

    for path in candidates:
        if path.is_file():
            from hdl_sim.parser.loader import read_verilog_text
            return read_verilog_text(path)

    msg = "verilog.lark grammar file not found (dev tree or PyInstaller bundle)"
    raise FileNotFoundError(msg)


@lru_cache(maxsize=1)
def _build_parser() -> Lark:
    grammar = _grammar_text()
    return Lark(
        grammar,
        parser="lalr",
        propagate_positions=False,
        maybe_placeholders=False,
    )


def parse_design(source: str) -> Design:
    """Parse Verilog source into a design with one or more modules."""

    normalized = normalize_source(source)
    tree = _build_parser().parse(normalized)
    design = VerilogTransformer().transform(tree)
    if not isinstance(design, Design):
        msg = "expected a design as the parse result"
        raise TypeError(msg)
    return design


def parse_module(source: str) -> Module:
    """Parse Verilog source and return the top module."""

    return parse_design(source).top
