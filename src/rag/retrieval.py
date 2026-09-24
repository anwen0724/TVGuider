"""Exact dense ranking and equal-weight reciprocal-rank fusion."""

from contextlib import closing

from qdrant_client import QdrantClient

from .contracts import StorageError


def rank_dense(generation, vector, count):
    """Retrieve all scores before stable sorting, including cutoff ties."""
    try:
        with closing(QdrantClient(path=str(generation / "qdrant"))) as client:
            points = client.query_points(
                "chunks", query=vector, limit=count, with_payload=False
            ).points
    except Exception as exc:
        raise StorageError(f"Vector retrieval failed: {exc}") from exc
    return sorted(
        [(str(point.id), float(point.score)) for point in points],
        key=lambda item: (-item[1], item[0]),
    )


def fuse(dense, lexical, rrf_k):
    """Return unique IDs with route ranks; missing routes contribute zero."""
    dr = {cid: i for i, (cid, _) in enumerate(dense, 1)}
    br = {cid: i for i, (cid, _) in enumerate(lexical, 1)}
    rows = [
        (
            cid,
            (1 / (rrf_k + dr[cid]) if cid in dr else 0)
            + (1 / (rrf_k + br[cid]) if cid in br else 0),
            dr.get(cid),
            br.get(cid),
        )
        for cid in dr.keys() | br.keys()
    ]
    return sorted(rows, key=lambda item: (-item[1], item[0]))
