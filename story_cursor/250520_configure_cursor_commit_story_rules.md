# Configure Cursor commit and story rules

**Date:** 2026-05-20  
**Task:** Configure Cursor to commit after each small task with a report, and save conversation stories to `story_cursor/` on each commit.

## What was done

- Added always-on Cursor rule `.cursor/rules/task-commit-and-story.mdc` defining the per-task workflow.
- Added PowerShell helper `.cursor/scripts/New-StoryPath.ps1` to build `YYMMDD_HHMM_shorttitle.md` filenames (shorttitle ≤50 chars).
- Documented story template, commit message format, and when to skip (no changes / user opts out).

## Files changed

- `.cursor/rules/task-commit-and-story.mdc` — agent workflow for story + commit after each task
- `.cursor/scripts/New-StoryPath.ps1` — filename generator for story markdown files

## User prompt

configure cursor that it should commit changes with report that what you have done after every small task done.


I want you to configure cursor that save our conversation as md file to story_cursor when you do git commit for each task. Also append my prompt at the end.
Md filename can be datetime_shorttitle.md. 
datetime means current time as yymmdd_hhss. shorttitle means abstraction title for our conversation. shorttitle length should not more than 50 letters.
