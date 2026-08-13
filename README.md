# Skill_Find 🧭

**Index and search local Python tools and skills by their docstrings — zero dependencies, pure Python stdlib.**

Skill_Find walks a directory tree, extracts the leading docstring from every `.py` file and the headings from every `README.md`, and writes a lightweight `index.json`. You can then search that index by token overlap and substring matching, or list everything that was indexed — an offline, dependency-free skill/tool finder for any agent or developer workspace.

## One tool, many domains

| Domain | What Skill_Find does for you |
|---|---|
| 🤖 **Agentic AI** | Lets agents discover what tools/skills live in a codebase without an LLM or network call — index once, query fast. |
| 🧑‍💻 **Developer Tooling** | A grep-with-scores over your project's own docstrings and READMEs, ranked by relevance instead of raw text hits. |
| 📚 **Knowledge Management** | Turns a pile of scripts and notes into a searchable local inventory of descriptions and headings. |

## Install

```bash
git clone git@github.com:realMNohgee/Skill_Find.git
cd Skill_Find
python3 Skill_Find.py --help
```

No dependencies — Python 3.8+ standard library only.

## Quick start

```bash
# Build an index from a directory tree
python3 Skill_Find.py index ~/projects/other-tool

# Search it (token overlap + substring scoring)
python3 Skill_Find.py search "audit log" -n 5

# Search as JSON for CI/pipelines
python3 Skill_Find.py search "audit log" --format json

# List everything that was indexed
python3 Skill_Find.py list
```

## License

MIT — see [LICENSE](LICENSE).

🧰 [Tool on Hermtica Marketplace](https://hermtica.com/marketplace)
