# {run} • Evaluation Import object changes

The HTML target: `{html_path}`  
Release ID: `{package_id}` · The number: `{round}` · {case_count}Case

The conventional concat-001The dragon evaluation file is a file that is a part of this HTML **Import**The original file and the HTML object, the production data were not changed.

## Bring the files.

- `{first_file}`
- `{second_file}`

Import one file from the star tab for each evaluator. Importing two evaluation files on the same screen continuously will replace the current execution judgment with the evaluator's judgment that was brought later.

## Changes to the content

1. `package_id`: concat-001The distribution ID of the actual object concat-002 The ID of HTML.
2. `run`: `20261003-concat-001` → `{run}`.
3. `cases`The real HTML: 1,260And I've sorted it into a list of cases and ordered it. `test-1111`Silver is falling. `test-0803`This includes the existing 1,000The list of evaluations in the cases is the same.
4. `conversion`The object HTML path, the description and the basis of the change. `03-round`And I kept it.

The existing values of each evaluator 1,000This is the first case. 7Type is = 7,000The judgement, key, check item, add/delete phrase, verify or not, evaluation view is the same. The original, modified, graph, verified data of the previous HTML and the HTML subject are compared, and the content and type-by-type snapshot are the same, except for run-path movements. 260The existing exclusion record is concat-001 It's stored in the conversion folder.

## The order of the readings and the verification data.

1. Upstairs two JSON: real import files.
2. `validation.json`: Original, corrected, and updated HTML hashes, content preservation and import inspection results.
3. `terminal.log`: Transform-check run log.
4. `target-package.json`: real HTML distribution, problem and model information.
5. `import-validator.cjs`: Verify the object HTML as the actual Import check function.

```shell
node annotation/20261001/import-20261003-concat-002/import-validator.cjs
# I'm going to check the actual importing test that I extracted from the target HTML and I'm gonna check two JSONs.
```

The viewer uses the HTML of the above object, and the JSON modification does not bypass the blocking rules of the HTML or change the definition of the creation data. `validation.json`I'm going to write it down separately.
