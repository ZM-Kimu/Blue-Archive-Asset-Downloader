import subprocess


class CommandUtils:
    @staticmethod
    def run_command(*commands: str, cwd: str | None = None) -> tuple[bool, str]:
        try:
            subprocess.run(
                list(commands),
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                check=True,
                text=True,
                cwd=cwd,
                encoding="utf8",
            )
            return True, ""
        except Exception as exc:
            error = (
                f"Command failed while execute command '{' '.join(list(commands))}' "
                f"with error: {exc}."
            )
            return False, error
