"""O catálogo canônico e o SPA não podem divergir.

`packages/common/common/catalog.py` é a fonte única do *conjunto* de tools. O SPA tem a própria
lista em `apps/web/src/data/tools.ts` e isso é legítimo: nome exibido, ícone e opções de formulário
são UI, não catálogo. O que **não** é legítimo é o conjunto de slugs divergir: adicionar uma tool no
canônico e esquecer o SPA (ou o contrário) só aparece quando o visitante clica num card que não
existe.

Este é o contrato: lê o `tools.ts` e falha se os slugs ou as categorias divergirem. A contagem
deixou de ser escrita à mão em cada arquivo — a igualdade abaixo é a asserção.
"""

import re
from pathlib import Path

from common.catalog import CATALOG

TOOLS_TS = Path(__file__).resolve().parents[3] / "apps" / "web" / "src" / "data" / "tools.ts"

SLUG = re.compile(r"slug:\s*'([a-z0-9-]+)'")
CATEGORY = re.compile(r"category:\s*'([a-z]+)'")


def spa_tools() -> dict[str, str]:
    """slug -> categoria, lido do fonte do SPA (cada entrada vai até o slug seguinte)."""
    text = TOOLS_TS.read_text()
    matches = list(SLUG.finditer(text))
    assert matches, f"nenhum tool encontrado em {TOOLS_TS} — o formato do arquivo mudou?"

    found: dict[str, str] = {}
    for index, match in enumerate(matches):
        end = matches[index + 1].start() if index + 1 < len(matches) else len(text)
        category = CATEGORY.search(text[match.end() : end])
        found[match.group(1)] = category.group(1) if category else "?"
    return found


def test_the_spa_lists_exactly_the_canonical_slugs() -> None:
    spa = set(spa_tools())
    canonical = set(CATALOG)
    assert spa == canonical, (
        f"só no SPA: {sorted(spa - canonical)} | só no canônico: {sorted(canonical - spa)}"
    )


def test_the_spa_category_matches_the_canonical_one() -> None:
    divergentes = {
        slug: (categoria, CATALOG[slug].category)
        for slug, categoria in spa_tools().items()
        if slug in CATALOG and categoria != CATALOG[slug].category
    }
    assert not divergentes, f"categoria divergente (SPA, canônico): {divergentes}"
