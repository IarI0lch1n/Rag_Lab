from dataclasses import dataclass


@dataclass(
    frozen=True
)
class ChunkingProfile:
    chunk_size: int
    chunk_overlap: int


CHUNKING_PROFILES = {

    #
    # Uploaded files.
    #
    # Smaller chunks because PDF/DOCX
    # usually contain dense information.
    #
    "file": ChunkingProfile(
        chunk_size=900,
        chunk_overlap=100,
    ),

    #
    # Website pages.
    #
    "web": ChunkingProfile(
        chunk_size=1400,
        chunk_overlap=150,
    ),

    #
    # Repository files.
    #
    "git": ChunkingProfile(
        chunk_size=1800,
        chunk_overlap=100,
    ),
}


DEFAULT_CHUNKING_PROFILE = (
    ChunkingProfile(
        chunk_size=1200,
        chunk_overlap=150,
    )
)


def get_chunking_profile(
    source_type: str,
) -> ChunkingProfile:

    return (
        CHUNKING_PROFILES.get(
            source_type,
            DEFAULT_CHUNKING_PROFILE,
        )
    )