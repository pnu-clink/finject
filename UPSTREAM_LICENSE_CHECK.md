# Upstream License Check

Checked on 2026-06-15.

Upstream resource:

- GitHub: https://github.com/BUPT-Reasoning/FinanceReasoning
- Paper: https://aclanthology.org/2025.acl-long.766/

Findings:

- The upstream GitHub repository is public.
- The upstream README states that the data and code for the FinanceReasoning paper are provided and describes the dataset files under the `data` directory.
- GitHub repository metadata reports no detected license.
- The GitHub license API endpoint returns `404 Not Found`.
- The repository root file listing does not include a `LICENSE` file.

Implication for FInject:

- The upstream dataset is publicly accessible, but no explicit open-source/open-data license was found.
- Until permission or license terms are clarified, do not describe FInject data as openly licensed.
- FInject includes the 78 answerable controls needed for paired evaluation and the 426 derived unanswerable variants, with attribution to FinanceReasoning.
- Before public DOI/Hugging Face release, confirm whether redistribution of the 78 controls and derived contexts is permitted, or obtain permission from the FinanceReasoning authors.
