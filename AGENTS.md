## Project Constraints

- All code must be written in English, including names, comments, error messages, CLI help text, and example commands.
- Documentation may be written in Chinese.

## Project Statement

- Network request code in this project is for learning purposes only.
- This project only parses game assets and does not involve illegal activities such as bypassing in-game anti-cheat systems.

## Workflow

- During implementation, keep the code style in English and prioritize reusing existing models, ports, boundaries, and project conventions.
- After completion, run the necessary formatting, type checks, and tests.
- The summary must explain the specific changes, the affected scenarios, and any compatibility risks introduced by the changes.

## Code and Compatibility

- Use type hints and prioritize readability; error handling must be traceable.
- Avoid import-time side effects, scattered magic values, and direct coupling to implementation details.
- Do not rename, remove, or change existing parameters without permission.
- Incompatible changes are allowed, but their scope and risks must be explained in advance.
- If anything is uncertain, ask the user; if confirmation cannot be obtained, stop the conversation.

## Testing

- Write only valuable tests that cover core functionality. Do not create low-value tests, such as documentation tests, without permission.

## Commit Messages

- Use Conventional Commits: `type(scope): concise summary`.
- Allowed types: `feat`, `fix`, `refactor`, `chore`, `docs`, `test`, `style`, `perf`, `ci`.
