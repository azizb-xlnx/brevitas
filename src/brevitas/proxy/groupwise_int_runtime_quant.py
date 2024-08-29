from typing import Union

from torch import Tensor

from brevitas.proxy.runtime_quant import ActQuantProxyFromInjector
from brevitas.quant_tensor import GroupwiseIntQuantTensor
from brevitas.quant_tensor import QuantTensor
from brevitas.utils.quant_utils import _CachedIOGroupwiseInt


class GroupwiseActQuantProxyFromInjector(ActQuantProxyFromInjector):

    @property
    def group_dim(self):
        return self.quant_injector.group_dim

    @property
    def group_size(self):
        return self.quant_injector.group_size

    def forward(self, x: Union[Tensor, QuantTensor]) -> Union[Tensor, GroupwiseIntQuantTensor]:
        out = x
        if self.fused_activation_quant_proxy is not None:
            y = x
            if isinstance(y, QuantTensor):
                y = y.value

            if self.export_mode:
                y = self.fused_activation_quant_proxy.activation_impl(y)
                y = self.export_handler(y)
            elif not self.is_quant_enabled:
                y = self.fused_activation_quant_proxy.activation_impl(y)
            else:
                y = self.fused_activation_quant_proxy(y)
            # If y is an empty GroupwiseIntQuantTensor, we need to check if this is a passthrough proxy,
            # otherwise return a simple Tensor
            # We exclude the last two values (inf_values and nan_values)
            if isinstance(y, tuple) and not any(map(lambda f: f is None, y[:-2])):
                value, scale, zero_point, bit_width, = y
                out = GroupwiseIntQuantTensor(
                    value,
                    scale,
                    zero_point,
                    self.group_size,
                    self.group_dim,
                    bit_width,
                    signed=self.is_signed,
                    training=self.training)
            elif self.is_passthrough_act:  # preserve scale/zp/bit/sign even without output quant
                if isinstance(y, tuple):
                    y = y[0]
                if isinstance(x, GroupwiseIntQuantTensor):
                    out = GroupwiseIntQuantTensor(
                        y,
                        x.scale,
                        x.zero_point,
                        self.group_size,
                        self.group_dim,
                        x.bit_width,
                        x.signed,
                        self.training)
                else:
                    out = y
            else:
                if isinstance(y, tuple):
                    y = y[0]
                out = y
        else:
            # If fused activation quant proxy is not enabled, return the input
            out = x
        if not self.training and self.cache_inference_quant_act and isinstance(
                out, GroupwiseIntQuantTensor):
            cached_out = _CachedIOGroupwiseInt(out.detach(), self.cache_quant_io_metadata_only)
            self._cached_act = cached_out
        return out