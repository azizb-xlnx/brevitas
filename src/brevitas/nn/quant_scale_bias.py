# Copyright (C) 2023, Advanced Micro Devices, Inc. All rights reserved.
# SPDX-License-Identifier: BSD-3-Clause

from typing import Optional, Type, Union

import torch
from torch import Tensor
from torch.nn import Module
from torch.nn import Parameter

from brevitas.function.ops import max_int
from brevitas.function.ops_ste import ceil_ste
from brevitas.inject.defaults import Int8WeightPerTensorFloat
from brevitas.quant_tensor import QuantTensor

from .quant_layer import ActQuantType
from .quant_layer import BiasQuantType
from .quant_layer import QuantWeightBiasInputOutputLayer as QuantWBIOL
from .quant_layer import WeightQuantType

__all__ = ['ScaleBias', 'QuantScaleBias']


class ScaleBias(Module):

    def __init__(self, num_features: int, bias: bool, runtime_shape=(1, -1, 1, 1)):
        super(ScaleBias, self).__init__()
        self.num_features = num_features
        self.weight = Parameter(torch.ones(num_features))
        self.bias = Parameter(torch.zeros(num_features)) if bias else None
        self.runtime_shape = runtime_shape

    def forward(self, input):
        out = input * self.weight.view(self.runtime_shape)
        if self.bias:
            out += self.bias.view(self.runtime_shape)
        return out


class QuantScaleBias(QuantWBIOL, ScaleBias):

    def __init__(
            self,
            num_features: int,
            bias: bool,
            weight_quant: Optional[WeightQuantType] = Int8WeightPerTensorFloat,
            bias_quant: Optional[BiasQuantType] = None,
            input_quant: Optional[ActQuantType] = None,
            output_quant: Optional[ActQuantType] = None,
            return_quant_tensor: bool = False,
            **kwargs) -> None:
        ScaleBias.__init__(self, num_features, bias)
        QuantWBIOL.__init__(
            self,
            weight_quant=weight_quant,
            bias_quant=bias_quant,
            input_quant=input_quant,
            output_quant=output_quant,
            return_quant_tensor=return_quant_tensor,
            **kwargs)

    @property
    def per_elem_ops(self):
        return 2

    @property
    def output_channel_dim(self):
        return 0

    @property
    def out_channels(self):
        return self.num_features

    @property
    def channelwise_separable(self) -> bool:
        return True

    def forward(self, inp: Union[Tensor, QuantTensor]) -> Union[Tensor, QuantTensor]:
        return self.forward_impl(inp)

    def inner_forward_impl(
            self,
            input: Union[Tensor, QuantTensor],
            quant_weight: Union[Tensor, QuantTensor],
            quant_bias: Optional[Union[Tensor, QuantTensor]]):
        quant_weight = quant_weight.view(self.runtime_shape)
        quant_bias = quant_bias.view(self.runtime_shape)

        def biased_mul(input, weight, bias):
            out = input * weight
            if bias is not None:
                out += bias
            return out

        output_tensor = biased_mul(input, quant_weight, quant_bias)

        return output_tensor
