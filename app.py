from studio.diagnostics import setup_logging, install_exception_hook

setup_logging()
install_exception_hook()

from studio.ui_v34 import run

if __name__ == '__main__':
    run()
