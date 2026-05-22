"""Abstract syntax tree nodes for the supported Verilog subset."""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum, auto


class DeclKind(Enum):
    REG = auto()
    WIRE = auto()
    INTEGER = auto()


class PortDirection(Enum):
    INPUT = auto()
    OUTPUT = auto()


class EdgeKind(Enum):
    POSEDGE = auto()
    NEGEDGE = auto()


@dataclass(frozen=True, slots=True)
class SourceLocation:
    line: int | None = None
    column: int | None = None


@dataclass(frozen=True, slots=True)
class ValueRange:
    msb: Expr
    lsb: Expr


@dataclass(frozen=True, slots=True)
class Range:
    msb: int
    lsb: int

    @property
    def width(self) -> int:
        return abs(self.msb - self.lsb) + 1


@dataclass(frozen=True, slots=True)
class Port:
    direction: PortDirection
    name: str
    range: ValueRange | None = None


@dataclass(frozen=True, slots=True)
class Declaration:
    kind: DeclKind
    name: str
    range: ValueRange | None = None
    loc: SourceLocation | None = None


class Expr:
    pass


@dataclass(frozen=True, slots=True)
class IntLiteral(Expr):
    value: int
    width: int | None = None
    x_mask: int = 0
    z_mask: int = 0


@dataclass(frozen=True, slots=True)
class FunctionCall(Expr):
    name: str
    args: tuple[Expr, ...]


@dataclass(frozen=True, slots=True)
class FunctionInput:
    name: str
    range: ValueRange | None = None


@dataclass(frozen=True, slots=True)
class FunctionDef:
    name: str
    return_range: ValueRange | None
    inputs: tuple[FunctionInput, ...]
    declarations: tuple[Declaration, ...]
    body_statements: tuple[Stmt, ...]


class TaskPortKind(Enum):
    INPUT = auto()
    OUTPUT = auto()


@dataclass(frozen=True, slots=True)
class TaskPort:
    kind: TaskPortKind
    name: str
    range: ValueRange | None = None


@dataclass(frozen=True, slots=True)
class TaskDef:
    name: str
    ports: tuple[TaskPort, ...]
    declarations: tuple[Declaration, ...]
    body_statements: tuple[Stmt, ...]


@dataclass(frozen=True, slots=True)
class IdentRef(Expr):
    name: str


@dataclass(frozen=True, slots=True)
class UnaryExpr(Expr):
    op: str
    operand: Expr


@dataclass(frozen=True, slots=True)
class BinaryExpr(Expr):
    op: str
    left: Expr
    right: Expr


@dataclass(frozen=True, slots=True)
class ConcatExpr(Expr):
    parts: tuple[Expr, ...]


class Stmt:
    pass


@dataclass(frozen=True, slots=True)
class TaskEnable(Stmt):
    name: str
    args: tuple[Expr, ...] = ()


@dataclass(frozen=True, slots=True)
class Block(Stmt):
    statements: tuple[Stmt, ...]


@dataclass(frozen=True, slots=True)
class Lvalue:
    base: str
    bit: Expr | None = None
    msb: Expr | None = None
    lsb: Expr | None = None


@dataclass(frozen=True, slots=True)
class BlockingAssign(Stmt):
    target: Lvalue
    expr: Expr


@dataclass(frozen=True, slots=True)
class NonBlockingAssign(Stmt):
    target: Lvalue
    expr: Expr


@dataclass(frozen=True, slots=True)
class DelayControl(Stmt):
    delay: int
    body: Stmt


@dataclass(frozen=True, slots=True)
class Forever(Stmt):
    body: Stmt


@dataclass(frozen=True, slots=True)
class Repeat(Stmt):
    count: int
    body: Stmt


@dataclass(frozen=True, slots=True)
class IfStmt(Stmt):
    condition: Expr
    then_branch: Stmt
    else_branch: Stmt | None = None


@dataclass(frozen=True, slots=True)
class EventControl(Stmt):
    events: tuple[Expr, ...]
    body: Stmt


@dataclass(frozen=True, slots=True)
class ContinuousAssign:
    target: str
    expr: Expr


@dataclass(frozen=True, slots=True)
class InitialBlock:
    body: Stmt


@dataclass(frozen=True, slots=True)
class AlwaysBlock:
    sensitivity: tuple[tuple[EdgeKind | None, str], ...] | None
    body: Stmt


@dataclass(frozen=True, slots=True)
class ParameterDecl:
    name: str
    expr: Expr


@dataclass(frozen=True, slots=True)
class ParameterOverride:
    name: str
    expr: Expr


@dataclass(frozen=True, slots=True)
class StringLiteral(Expr):
    value: str


@dataclass(frozen=True, slots=True)
class DisplayArg:
    text: str | None = None
    expr: Expr | None = None



@dataclass(frozen=True, slots=True)
class BitSelect(Expr):
    signal: str
    index: Expr


@dataclass(frozen=True, slots=True)
class PartSelect(Expr):
    signal: str
    msb: Expr
    lsb: Expr


@dataclass(frozen=True, slots=True)
class CaseItem:
    expressions: tuple[Expr, ...]
    body: Stmt


@dataclass(frozen=True, slots=True)
class CaseStmt(Stmt):
    expression: Expr
    items: tuple[CaseItem, ...]
    case_style: str = "case"


@dataclass(frozen=True, slots=True)
class ForStmt(Stmt):
    init: BlockingAssign | None
    condition: Expr | None
    step: BlockingAssign | None
    body: Stmt


@dataclass(frozen=True, slots=True)
class WhileStmt(Stmt):
    condition: Expr
    body: Stmt


@dataclass(frozen=True, slots=True)
class SystemTask(Stmt):
    name: str
    args: tuple[DisplayArg, ...] = ()

@dataclass(frozen=True, slots=True)
class Display(Stmt):
    args: tuple[DisplayArg, ...]


@dataclass(frozen=True, slots=True)
class PortConnection:
    port: str
    expr: Expr


@dataclass(frozen=True, slots=True)
class ModuleInstance:
    module_type: str
    instance_name: str
    parameter_overrides: tuple[ParameterOverride, ...] = ()
    connections: tuple[PortConnection, ...] = ()


@dataclass(frozen=True, slots=True)
class Module:
    name: str
    parameters: tuple[ParameterDecl, ...] = ()
    ports: tuple[Port, ...] = ()
    declarations: tuple[Declaration, ...] = ()
    continuous_assigns: tuple[ContinuousAssign, ...] = ()
    initial_blocks: tuple[InitialBlock, ...] = ()
    always_blocks: tuple[AlwaysBlock, ...] = ()
    instances: tuple[ModuleInstance, ...] = ()
    functions: tuple[FunctionDef, ...] = ()
    tasks: tuple[TaskDef, ...] = ()
    loc: SourceLocation | None = None


@dataclass(frozen=True, slots=True)
class Design:
    modules: tuple[Module, ...] = field(default_factory=tuple)

    def module_by_name(self, name: str) -> Module:
        for module in self.modules:
            if module.name == name:
                return module
        msg = f"unknown module: {name}"
        raise ValueError(msg)

    @property
    def top(self) -> Module:
        referenced = {instance.module_type for module in self.modules for instance in module.instances}
        roots = [module for module in self.modules if module.name not in referenced]
        if len(roots) == 1:
            return roots[0]
        if len(self.modules) == 1:
            return self.modules[0]
        msg = f"unable to determine top module (candidates: {[m.name for m in roots]})"
        raise ValueError(msg)
