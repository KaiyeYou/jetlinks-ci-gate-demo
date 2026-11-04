# AI Code Review Contract

Review the pull request as an advisory reviewer. Do not approve or reject the
pull request. Report only findings that can be tied to changed lines and a
repository contract.

For every finding provide:

1. severity and changed line;
2. violated contract or evidence;
3. concrete runtime consequence;
4. a verification step or missing test;
5. whether a human business decision is required.

Repository contract for this demo:

- A device export must be bounded.
- The maximum synchronous export is 5,000 rows, inclusive.
- Values above 5,000 must use an asynchronous export job.
- AI findings are advisory; a human reviewer owns the merge decision.
