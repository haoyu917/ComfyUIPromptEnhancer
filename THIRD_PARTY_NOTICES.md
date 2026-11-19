# Third-Party Notices

## Three-way decision with granular rough sets (academic reference)

The offline research code in `research/` implements methods described in:

> Junfang Luo, Mengjun Hu, Chengjun Shi, Yiyu Yao. "Three-way decision with granular rough sets." *Applied Soft Computing* 180 (2025) 113344. https://doi.org/10.1016/j.asoc.2025.113344

- The article is published open access under the **Creative Commons Attribution-NonCommercial-NoDerivatives 4.0** license (CC BY-NC-ND 4.0), https://creativecommons.org/licenses/by-nc-nd/4.0/.
- `research/granular_3wd.py` is an independently written implementation of the definitions and algorithm described in the article; it does not reproduce the article's text or figures.
- `tests/test_granular_3wd.py` reproduces, for verification only, the article's small set-valued example table (Table 2), its test objects (Tables 3 to 6), and the example results stated in Section 4, with this attribution. These excerpts remain under the article's license; they are not part of the ComfyUI node and are not covered by any license of this repository.
- Citing the article does not imply that its authors endorse or are involved in this project.

## Cinematic Director Skill v2.0

BUFF AI · Modular Director Skill Engine V3 includes a compact adaptation of directing methodology described by **Cinematic Director Skill v2.0**. The upstream project is distributed under the MIT License. Its copyright and permission notice is reproduced in `LICENSES/CINEMATIC_DIRECTOR_SKILL_MIT.txt`.

- Original project: `wuwangzhang1216/DirectorSKILL`
- Author/copyright holder: **wangzhang-wu**
- License: **MIT License**
- Original project URL: https://github.com/wuwangzhang1216/DirectorSKILL

The adaptation uses high-level methods such as story-function-first shot design, blocking before framing, observable performance direction, continuity planning, keyframe strategy, sound and dialogue planning, model-adapter routing, and quality-control reasoning. It does not include specific shots, dialogue, characters, plots, or other copyrighted expression from existing films.

The upstream license notice is included here for the credited upstream material. It does not grant a license to BUFF AI's independently authored code or documentation. This repository currently has no declared project-wide license; see the License section in `README.md`.

Upstream source: https://github.com/wuwangzhang1216/DirectorSKILL
