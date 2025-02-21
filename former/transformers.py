import torch
from torch import nn
import torch.nn.functional as F

from .modules import TransformerBlock

from .util import d


class GTransformer(nn.Module):
    """
    Transformer for generating text (character by character).
    """

    def __init__(self, emb, heads, depth, seq_length, num_tokens):
        super().__init__()

        self.num_tokens = num_tokens
        self.token_embedding = nn.Embedding(
            embedding_dim=emb, num_embeddings=num_tokens
        )
        self.pos_embedding = nn.Embedding(
            embedding_dim=emb, num_embeddings=seq_length
        )

        tblocks = []
        for i in range(depth):
            tblocks.append(
                TransformerBlock(
                    emb=emb, heads=heads, seq_length=seq_length, mask=True
                )
            )

        self.tblocks = nn.Sequential(*tblocks)

        self.toprobs = nn.Linear(emb, num_tokens)

    def forward(self, x):
        """
        :param x: A batch by sequence length integer tensor of token indices.
        :return: predicted log-probability vectors for each token based on the preceding tokens.
        """
        tokens = self.token_embedding(x)
        b, t, e = tokens.size()

        # original device is set to d()
        positions = self.pos_embedding(torch.arange(t, device=tokens.device))[
            None, :, :
        ].expand(b, t, e)
        x = tokens + positions

        x = self.tblocks(x)

        x = self.toprobs(x.view(b * t, e)).view(b, t, self.num_tokens)

        return F.log_softmax(x, dim=2)


class CTransformer(nn.Module):
    """
    Transformer for classifying sequences
    """

    def __init__(
        self,
        emb,
        heads,
        depth,
        seq_length,
        num_tokens,
        num_classes,
        max_pool=True,
        dropout=0.0,
    ):
        """
        :param emb: Embedding dimension
        :param heads: nr. of attention heads
        :param depth: Number of transformer blocks
        :param seq_length: Expected maximum sequence length
        :param num_tokens: Number of tokens (usually words) in the vocabulary
        :param num_classes: Number of classes.
        :param max_pool: If true, use global max pooling in the last layer. If false, use global
                         average pooling.
        """
        super().__init__()

        self.num_tokens, self.max_pool = num_tokens, max_pool

        self.token_embedding = nn.Embedding(
            embedding_dim=emb, num_embeddings=num_tokens
        )
        self.pos_embedding = nn.Embedding(
            embedding_dim=emb, num_embeddings=seq_length
        )

        tblocks = []
        for i in range(depth):
            tblocks.append(
                TransformerBlock(
                    emb=emb,
                    heads=heads,
                    seq_length=seq_length,
                    mask=False,
                    dropout=dropout,
                )
            )

        self.tblocks = nn.Sequential(*tblocks)

        self.toprobs = nn.Linear(emb, num_classes)

        self.do = nn.Dropout(dropout)

    def forward(self, x):
        """
        :param x: A batch by sequence length integer tensor of token indices.
        :return: predicted log-probability vectors for each token based on the preceding tokens.
        """
        tokens = self.token_embedding(x)
        b, t, e = tokens.size()

        positions = self.pos_embedding(torch.arange(t, device=tokens.device))[
            None, :, :
        ].expand(b, t, e)
        x = tokens + positions
        x = self.do(x)

        x = self.tblocks(x)

        x = (
            x.max(dim=1)[0] if self.max_pool else x.mean(dim=1)
        )  # pool over the time dimension

        x = self.toprobs(x)

        return F.log_softmax(x, dim=1)


class TSTransformer(nn.Module):
    """
    Transformer for classifying sequences
    """

    def __init__(
        self,
        # emb,
        feature_dim: int,
        heads: int,
        depth: int,
        seq_length: int,
        # num_tokens,
        num_classes: int,
        max_pool: bool = True,
        dropout: float = 0.0,
    ):
        """
        A time series transfomrmer that can handle both numerical and
        categorical features. Cat features are converted into entity embeddings.

        :param emb: Embedding dimension
        :param heads: nr. of attention heads
        :param depth: Number of transformer blocks
        :param seq_length: Expected maximum sequence length
        # :param num_tokens: Number of tokens (usually words) in the vocabulary
        :param num_classes: Number of classes.
        :param max_pool: If true, use global max pooling in the last layer.
            If false, use global
                         average pooling.
        """
        super().__init__()

        # self.num_tokens = num_tokens
        self.max_pool = max_pool

        # don't need token embedding as input is numerical, but with dim > 1
        # self.token_embedding = nn.Embedding(
        #     embedding_dim=emb, num_embeddings=num_tokens
        # )
        # how to use positional embedding?
        self.pos_embedding = nn.Embedding(
            embedding_dim=feature_dim, num_embeddings=seq_length
        )

        tblocks = []
        for i in range(depth):
            tblocks.append(
                TransformerBlock(
                    emb=feature_dim,
                    heads=heads,
                    seq_length=seq_length,
                    mask=True,
                    dropout=dropout,
                )
            )

        self.tblocks = nn.Sequential(*tblocks)

        self.toprobs = nn.Linear(feature_dim, num_classes)

        self.do = nn.Dropout(dropout)

    def forward(self, x):
        """
        :param x: A batch by sequence length integer tensor of token indices.
        :return: predicted log-probability vectors for each token based on the
        preceding tokens.
        """
        # tokens = self.token_embedding(x)
        # b, t, e = tokens.size()
        b, t, e = x.shape

        positions = self.pos_embedding(torch.arange(t, device=d()))[
            None, :, :
        ].expand(b, t, e)
        x = x + positions
        x = self.do(x)

        x = self.tblocks(x)

        x = (
            x.max(dim=1)[0] if self.max_pool else x.mean(dim=1)
        )  # pool over the time dimension

        x = self.toprobs(x)

        return F.log_softmax(x, dim=1)


class TSRegTransformer(nn.Module):
    """
    Transformer for regression problems.
    """

    def __init__(
        self,
        # emb,
        feature_dim: int,
        heads: int,
        depth: int,
        seq_length: int,
        # num_tokens,
        # num_classes: int,
        out_dim: int,
        max_pool: bool = True,
        dropout: float = 0.0,
    ):
        """
        A time series transfomrmer that can handle both numerical and
        categorical features. Cat features are converted into entity embeddings.

        :param emb: Embedding dimension
        :param heads: nr. of attention heads
        :param depth: Number of transformer blocks
        :param seq_length: Expected maximum sequence length
        # :param num_tokens: Number of tokens (usually words) in the vocabulary
        :param out_dim: regression output dimension.
        :param max_pool: If true, use global max pooling in the last layer.
            If false, use global
                         average pooling.
        """
        super().__init__()

        # self.num_tokens = num_tokens
        self.max_pool = max_pool

        # don't need token embedding as input is numerical, but with dim > 1
        # self.token_embedding = nn.Embedding(
        #     embedding_dim=emb, num_embeddings=num_tokens
        # )
        # how to use positional embedding?
        self.pos_embedding = nn.Embedding(
            embedding_dim=feature_dim, num_embeddings=seq_length
        )

        tblocks = []
        for i in range(depth):
            tblocks.append(
                TransformerBlock(
                    emb=feature_dim,
                    heads=heads,
                    seq_length=seq_length,
                    mask=True,
                    dropout=dropout,
                )
            )

        self.tblocks = nn.Sequential(*tblocks)

        self.linear_output = nn.Linear(feature_dim, out_dim)

        self.do = nn.Dropout(dropout)

    def forward(self, x):
        """
        :param x: A batch by sequence length integer tensor of token indices.
        :return: predicted log-probability vectors for each token based on the
        preceding tokens.
        """
        # tokens = self.token_embedding(x)
        # b, t, e = tokens.size()
        b, t, e = x.shape

        # place positional encoding onto the same device
        positions = self.pos_embedding(torch.arange(t, device=x.device))[
            None, :, :
        ].expand(b, t, e)
        x = x.float() + positions
        x = self.do(x)

        x = self.tblocks(x)

        x = (
            x.max(dim=1)[0] if self.max_pool else x.mean(dim=1)
        )  # pool over the time dimension

        x = self.linear_output(x)

        return x
