from __future__ import absolute_import, division, print_function, unicode_literals
import torch
from ...modules.module import Module
from ...._jit_internal import weak_module

@weak_module
class Linear(Module):
    r"""
    A module that wraps the quantized fbgemm linear operator function
    We adopt the same interface as `torch.nn.Linear`, please see https://pytorch.org/docs/stable/nn.html#torch.nn.Linear
    for documentation.

    Similar to `torch.nn.Linear`, attributes will be randomly initialized at
        module creation time and will be overwritten later

    Attributes:
        _packed_weight: the non-learnable packed weights of the
            module which are of shape :math:`(\text{out\_features}, \text{in\_features})`.
        bias:   the non-learnable bias of the module of shape :math:`(\text{out\_features})`.
                If :attr:`bias` is ``True``, the values are initialized to zero.
        output_scale: `scale` parameter of output Quantized Tensor
        output_zero_point: `zero_point` parameter for output Quantized Tensor

    Examples::

        >>> m = nn.quantized.Linear(20, 30)
        >>> input = torch.randn(128, 20)
        >>> output = m(input)
        >>> print(output.size())
        torch.Size([128, 30])
    """
    __constants__ = ['bias', 'in_features', 'out_features']

    def __init__(self, in_features, out_features, bias=True):
        super(Linear, self).__init__()
        weight = torch.randn(out_features, in_features, dtype=torch.float32)
        weight = torch.quantize_linear(weight, 1.0, 0, torch.qint8)
        _packed_weight = torch.ops.quantized.fbgemm_linear_prepack(weight)

        output_scale = 1.0
        self.register_buffer('output_scale', torch.Tensor([output_scale]))
        output_zero_point = 0
        self.register_buffer('output_zero_point', torch.Tensor([output_zero_point]))
        self.register_buffer('_packed_weight', _packed_weight)
        _bias = torch.quantize_linear(torch.zeros(out_features).float(), output_scale,
                                      output_zero_point, torch.qint32)
        self.register_buffer('bias', _bias)


    def forward(self, x):
        Y_q = torch.ops.quantized.fbgemm_linear(x, self._packed_weight, self.bias, self.output_scale, self.output_zero_point)
        return Y_q

    # TODO: remove after https://github.com/pytorch/pytorch/pull/21933 is landed
    def state_dict(self, destination=None, prefix='', keep_vars=False):
        r"""
        Example::

            >>> module.state_dict().keys()
            ['bias', 'weight']

        """
        raw_dict = super().state_dict(destination, prefix, keep_vars)
        weight = torch.ops.quantized.fbgemm_linear_unpack(raw_dict[prefix + '_packed_weight'])
        raw_dict[prefix + 'weight'] = weight
        raw_dict.pop(prefix + '_packed_weight')
        return raw_dict

    # def _save_to_state_dict(self, destination, prefix, keep_vars):
    #     super()._save_to_state_dict(destination, prefix, keep_vars)
    #     destination[prefix + 'weight'] = torch.ops.quantized.fbgemm_linear_unpack(destination[prefix + '_packed_weight'])
    #     destination.pop(prefix + '_packed_weight')

    def _load_from_state_dict(self, state_dict, prefix, local_metadata, strict,
                              missing_keys, unexpected_keys, error_msgs):
        r"""
            Modify state_dict first and then use default load function
        """
        self._packed_weight = torch.ops.quantized.fbgemm_linear_prepack(state_dict[prefix + 'weight'])
        self.bias = state_dict[prefix + 'bias']
        # state_dict.pop(prefix + 'weight')
        super()._load_from_state_dict(state_dict, prefix, local_metadata, False,
                                      missing_keys, unexpected_keys, error_msgs)
        return