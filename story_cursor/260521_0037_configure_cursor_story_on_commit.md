# Configure Cursor story on commit

**Date:** 2026-05-21  
**Task:** Configure Cursor to save each task conversation to `story_cursor/` as markdown when committing, with the user prompt appended at the end.

## What was done

- Confirmed always-on rule `.cursor/rules/task-commit-and-story.mdc` already defines per-task story + git commit workflow.
- Aligned datetime wording in the rule with `configure_cursor` (`yymmdd_hhss` → `YYMMDD_HHMM` for filenames).
- Confirmed `New-StoryPath.ps1` builds `story_cursor/{datetime}_{shorttitle}.md` with shorttitle ≤50 chars.
- Story template includes a **User prompt** section at the end (verbatim user message).

## Files changed

- `.cursor/rules/task-commit-and-story.mdc` — datetime label aligned with `configure_cursor`
- `story_cursor/260521_0037_configure_cursor_story_on_commit.md` — this task story

## User prompt

@configure_cursor (1-4) 
