"""Elaborate parsed modules into a flat simulation netlist."""

from __future__ import annotations

from dataclasses import dataclass

from hdl_sim.engine.nets import SimNet
from hdl_sim.engine.generate import expand_module_generates
from hdl_sim.engine.params import ParameterEvaluator
from hdl_sim.parser.ast import (
    FunctionDef,
    TaskDef,
    AlwaysBlock,
    BitSelect,
    ContinuousAssign,
    DeclKind,
    Design,
    Expr,
    IdentRef,
    InitialBlock,
    Module,
    ModuleInstance,
    PartSelect,
    PortConnection,
    PortDirection,
    Stmt,
)


@dataclass(frozen=True, slots=True)
class ScopedContinuousAssign:
    target: str
    expr: Expr
    locals: dict[str, SimNet]
    params: dict[str, int]


@dataclass(frozen=True, slots=True)
class ScopedProcess:
    body: Stmt
    locals: dict[str, SimNet]
    params: dict[str, int]


@dataclass(frozen=True, slots=True)
class ElaboratedDesign:
    """Flattened design ready for simulation."""

    top_module: str
    nets: dict[str, SimNet]
    continuous_assigns: tuple[ScopedContinuousAssign, ...]
    initial_blocks: tuple[ScopedProcess, ...]
    always_blocks: tuple[tuple[AlwaysBlock, dict[str, SimNet], dict[str, int]], ...]
    functions: tuple[FunctionDef, ...] = ()
    tasks: tuple[TaskDef, ...] = ()


def elaborate(design: Design, *, top: str | None = None) -> ElaboratedDesign:
    modules = {module.name: module for module in design.modules}
    top = design.module_by_name(top) if top else design.top
    global_nets: dict[str, SimNet] = {}
    continuous: list[ScopedContinuousAssign] = []
    initials: list[ScopedProcess] = []
    always_blocks: list[tuple[AlwaysBlock, dict[str, SimNet], dict[str, int]]] = []

    functions_map: dict[str, FunctionDef] = {}
    tasks_map: dict[str, TaskDef] = {}
    for module in design.modules:
        for func in module.functions:
            functions_map[func.name] = func
        for task in module.tasks:
            tasks_map[task.name] = task
    functions = tuple(functions_map.values())
    tasks = tuple(tasks_map.values())

    _elaborate_module(
        top,
        modules=modules,
        global_nets=global_nets,
        prefix="",
        param_env={},
        continuous=continuous,
        initials=initials,
        always_blocks=always_blocks,
    )

    return ElaboratedDesign(
        top_module=top.name,
        nets=global_nets,
        continuous_assigns=tuple(continuous),
        initial_blocks=tuple(initials),
        always_blocks=tuple(always_blocks),
        functions=functions,
        tasks=tasks,
    )


def _elaborate_module(
    module: Module,
    *,
    modules: dict[str, Module],
    global_nets: dict[str, SimNet],
    prefix: str,
    continuous: list[ScopedContinuousAssign],
    initials: list[ScopedProcess],
    always_blocks: list[tuple[AlwaysBlock, dict[str, SimNet], dict[str, int]]],
    port_bindings: dict[str, SimNet] | None = None,
    param_env: dict[str, int] | None = None,
) -> dict[str, SimNet]:
    local: dict[str, SimNet] = {}
    param_evaluator = ParameterEvaluator(param_env)
    param_evaluator.resolve_module_params(module.parameters)
    module = expand_module_generates(module, param_evaluator)

    for param_name, param_value in param_evaluator.snapshot().items():
        local[param_name] = SimNet(
            name=_scoped_name(prefix, param_name),
            width=32,
            kind=DeclKind.INTEGER,
            value=param_value,
        )

    for port in module.ports:
        if port_bindings and port.name in port_bindings:
            net = port_bindings[port.name]
        else:
            full_name = _scoped_name(prefix, port.name)
            if port.net_kind is not None:
                kind = port.net_kind
            elif port.direction in (PortDirection.INPUT, PortDirection.INOUT):
                kind = DeclKind.WIRE
            else:
                kind = DeclKind.REG
            net = SimNet.from_declaration(
                full_name,
                kind,
                param_evaluator.resolve_range(port.range),
                is_signed=port.is_signed,
            )
            global_nets[full_name] = net
        local[port.name] = net

    for decl in module.declarations:
        if decl.name in local:
            continue
        full_name = _scoped_name(prefix, decl.name)
        net = SimNet.from_declaration(
            full_name,
            decl.kind,
            param_evaluator.resolve_range(decl.range),
            unpacked_range=(
                param_evaluator.resolve_range(decl.unpacked_range)
                if decl.unpacked_range is not None
                else None
            ),
            is_signed=decl.is_signed,
        )
        local[decl.name] = net
        global_nets[full_name] = net

    module_params = param_evaluator.snapshot()

    for assign in module.continuous_assigns:
        target = _scoped_name(prefix, assign.target)
        if assign.target in local:
            global_nets[target] = local[assign.target]
        elif target not in global_nets:
            global_nets[target] = SimNet(name=target, width=1, kind=DeclKind.WIRE)
            local[assign.target] = global_nets[target]
        continuous.append(
            ScopedContinuousAssign(
                target=target,
                expr=assign.expr,
                locals=dict(local),
                params=dict(module_params),
            )
        )

    for block in module.initial_blocks:
        initials.append(ScopedProcess(body=block.body, locals=dict(local), params=dict(module_params)))

    for block in module.always_blocks:
        always_blocks.append((block, dict(local), dict(module_params)))

    for instance in module.instances:
        child = modules[instance.module_type]
        child_prefix = _scoped_name(prefix, instance.instance_name)
        bindings = _resolve_instance_ports(
            instance,
            child,
            local,
            prefix,
            global_nets,
            child_prefix=child_prefix,
            param_evaluator=param_evaluator,
            continuous=continuous,
            module_params=module_params,
        )
        child_params = ParameterEvaluator(param_evaluator.snapshot()).resolve_module_params(
            child.parameters,
            instance.parameter_overrides,
        )
        _elaborate_module(
            child,
            modules=modules,
            global_nets=global_nets,
            prefix=child_prefix,
            continuous=continuous,
            initials=initials,
            always_blocks=always_blocks,
            port_bindings=bindings,
            param_env=child_params,
        )

    return local


def _resolve_instance_ports(
    instance: ModuleInstance,
    child: Module,
    parent_local: dict[str, SimNet],
    parent_prefix: str,
    global_nets: dict[str, SimNet],
    *,
    child_prefix: str,
    param_evaluator: ParameterEvaluator,
    continuous: list[ScopedContinuousAssign],
    module_params: dict[str, int],
) -> dict[str, SimNet]:
    bindings: dict[str, SimNet] = {}
    port_names = [p.name for p in child.ports]
    port_dirs = {p.name: p.direction for p in child.ports}
    for index, connection in enumerate(instance.connections):
        port_name = connection.port or (
            port_names[index] if index < len(port_names) else ""
        )
        if not port_name:
            msg = f"positional port connection out of range for {instance.module_type}"
            raise ValueError(msg)
        direction = port_dirs.get(port_name, PortDirection.INPUT)
        bindings[port_name] = _resolve_connection_expr(
            connection,
            parent_local,
            parent_prefix,
            global_nets,
            child_prefix=child_prefix,
            port_name=port_name,
            port_direction=direction,
            param_evaluator=param_evaluator,
            continuous=continuous,
            module_params=module_params,
        )
    return bindings


def _lookup_parent_net(
    name: str,
    parent_local: dict[str, SimNet],
    parent_prefix: str,
    global_nets: dict[str, SimNet],
) -> SimNet:
    if name in parent_local:
        return parent_local[name]
    full_name = _scoped_name(parent_prefix, name)
    if full_name in global_nets:
        return global_nets[full_name]
    msg = f"unknown connection signal: {name}"
    raise ValueError(msg)


def _resolve_connection_expr(
    connection: PortConnection,
    parent_local: dict[str, SimNet],
    parent_prefix: str,
    global_nets: dict[str, SimNet],
    *,
    child_prefix: str,
    port_name: str,
    port_direction: PortDirection,
    param_evaluator: ParameterEvaluator,
    continuous: list[ScopedContinuousAssign],
    module_params: dict[str, int],
) -> SimNet:
    expr = connection.expr
    if isinstance(expr, IdentRef):
        return _lookup_parent_net(expr.name, parent_local, parent_prefix, global_nets)
    if isinstance(expr, BitSelect):
        expr = PartSelect(signal=expr.signal, msb=expr.index, lsb=expr.index, word=expr.word)
    if isinstance(expr, PartSelect):
        return _resolve_slice_port_connection(
            expr,
            parent_local,
            parent_prefix,
            global_nets,
            child_prefix=child_prefix,
            port_name=port_name,
            port_direction=port_direction,
            param_evaluator=param_evaluator,
            continuous=continuous,
            module_params=module_params,
        )
    msg = f"unsupported port connection expression for {connection.port or port_name}"
    raise ValueError(msg)


def _resolve_slice_port_connection(
    expr: PartSelect,
    parent_local: dict[str, SimNet],
    parent_prefix: str,
    global_nets: dict[str, SimNet],
    *,
    child_prefix: str,
    port_name: str,
    port_direction: PortDirection,
    param_evaluator: ParameterEvaluator,
    continuous: list[ScopedContinuousAssign],
    module_params: dict[str, int],
) -> SimNet:
    _lookup_parent_net(expr.signal, parent_local, parent_prefix, global_nets)
    msb = param_evaluator.eval(expr.msb)
    lsb = param_evaluator.eval(expr.lsb)
    if msb < lsb:
        msb, lsb = lsb, msb
    slice_width = msb - lsb + 1

    port_full = _scoped_name(child_prefix, port_name)
    port_net = SimNet(name=port_full, width=slice_width, kind=DeclKind.WIRE)
    global_nets[port_full] = port_net

    if port_direction is PortDirection.OUTPUT:
        msg = (
            f"output port {port_name} connected to slice {expr.signal}[{msb}:{lsb}] "
            "is not supported yet"
        )
        raise ValueError(msg)

    if port_direction is PortDirection.INOUT:
        msg = f"inout port slice connection for {port_name} is not supported yet"
        raise ValueError(msg)

    continuous.append(
        ScopedContinuousAssign(
            target=port_full,
            expr=expr,
            locals=dict(parent_local),
            params=dict(module_params),
        )
    )
    return port_net


def _scoped_name(prefix: str, name: str) -> str:
    if not prefix:
        return name
    return f"{prefix}.{name}"
