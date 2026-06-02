"""Non-ANSI Verilog port lists (names only in module header)."""

from hdl_sim.parser import parse_module
from hdl_sim.parser.ast import PortDirection


def test_implicit_port_list_with_body_directions() -> None:
    module = parse_module(
        """
        module sai (ck, reset, enable, lamp);
          input ck;
          input reset;
          input enable;
          output lamp;
        endmodule
        """
    )
    assert module.name == "sai"
    assert len(module.ports) == 4
    by_name = {p.name: p.direction for p in module.ports}
    assert by_name["ck"] is PortDirection.INPUT
    assert by_name["lamp"] is PortDirection.OUTPUT
