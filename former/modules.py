from former import util
from .util import mask_

import torch
from torch import nn
import torch.nn.functional as F

# import random,
import math


class SelfAttention(nn.Module):
    def __init__(self, emb, heads=8, mask=False):
        """

        :param emb:
        :param heads:
        :param mask:
        """

        super().__init__()

        self.emb = emb
        self.heads = heads
        self.mask = mask

        self.tokeys = nn.Linear(emb, emb * heads, bias=False)
        self.toqueries = nn.Linear(emb, emb * heads, bias=False)
        self.tovalues = nn.Linear(emb, emb * heads, bias=False)

        self.unifyheads = nn.Linear(heads * emb, emb)

    def forward(self, x):

        b, t, e = x.size()
        h = self.heads
        assert (
            e == self.emb
        ), f"Input embedding dim ({e}) should match layer embedding dim ({self.emb})"

        keys = self.tokeys(x).view(b, t, h, e)
        queries = self.toqueries(x).view(b, t, h, e)
        values = self.tovalues(x).view(b, t, h, e)

        # compute scaled dot-product self-attention

        # - fold heads into the batch dimension
        keys = keys.transpose(1, 2).contiguous().view(b * h, t, e)
        queries = queries.transpose(1, 2).contiguous().view(b * h, t, e)
        values = values.transpose(1, 2).contiguous().view(b * h, t, e)

        # replaced original code that divides both queries and keys
        # doing it once is enough and produces the same results since
        # they are multiplied together.
        queries = queries / math.sqrt(e)
        # queries = queries / math.pow(e, 0.25)
        # keys = keys / math.pow(e, 0.25)

        # Instead of dividing the dot products by sqrt(e), we scale the keys
        # and values.
        # This should be more memory efficient
        # see https://github.com/pbloem/former/issues/5 for explanation on
        # when this would be more memory efficient - i.e. when t >> e

        # - get dot product of queries and keys, and scale
        dot = torch.bmm(queries, keys.transpose(1, 2))

        assert dot.size() == (
            b * h,
            t,
            t,
        ), f"Matrix has size {dot.size()}, expected {(b*h, t, t)}."

        if self.mask:
            # mask out the upper half of the dot matrix, excluding the diagonal
            mask_(dot, maskval=float("-inf"), mask_diagonal=False)

        dot = F.softmax(dot, dim=2)
        # dot now has row-wise self-attention probabilities

        # assert not util.contains_nan(dot[:, 1:, :])
        # assert not torch.isnan(dot[:, 1:, :]).any()
        # only the forst row may contain nan

        # if self.mask == "first":
        #     dot = dot.clone()
        #     dot[:, :1, :] = 0.0
        #     # The first row of the first attention matrix is entirely masked
        #     # out, so the softmax operation results in a division by zero.
        #     # We set this row to zero by hand to get rid of the NaNs

        # apply the self attention to the values
        out = torch.bmm(dot, values).view(b, h, t, e)

        # swap h, t back, unify heads
        out = out.transpose(1, 2).contiguous().view(b, t, h * e)

        return self.unifyheads(out)


class TransformerBlock(nn.Module):
    def __init__(
        self, emb, heads, mask, seq_length, ff_hidden_mult=4, dropout=0.0
    ):
        super().__init__()

        self.attention = SelfAttention(emb, heads=heads, mask=mask)
        self.mask = mask

        self.norm1 = nn.LayerNorm(emb)
        self.norm2 = nn.LayerNorm(emb)

        self.ff = nn.Sequential(
            nn.Linear(emb, ff_hidden_mult * emb),
            nn.ReLU(),
            nn.Linear(ff_hidden_mult * emb, emb),
        )

        self.do = nn.Dropout(dropout)

    def forward(self, x):

        attended = self.attention(x)

        x = self.norm1(attended + x)

        x = self.do(x)

        fedforward = self.ff(x)

        x = self.norm2(fedforward + x)

        x = self.do(x)

        return x
