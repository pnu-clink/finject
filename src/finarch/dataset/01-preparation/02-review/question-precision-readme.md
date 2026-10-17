# Question number test and LLM correction

Python verifies the correspondence of gold·precision and the explicit number of digits in the question, and does not change the question first. It passes the original Q·C·A and reference_answer_type·reference_precision to the existing audit.

If there's a discrepancy, we'll pass the same QCA-type-precision to the existing preparation.revise and get a question correction. 1It gives you the opportunity to rectify, and the numerical and resource positioning checks only allow for digit changes, re-evaluate the modified QCA, and save comparisons to the original data.json for work after passing. POT requests don't add gold.

01-check.json is the basis for Python testing. 02-LLM-revise-text and 03Check-revision to check the raw response and the post-correction. 02-review-and-correct, and then you can see the file and the QCA diff.
