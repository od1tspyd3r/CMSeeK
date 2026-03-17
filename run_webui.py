#!/usr/bin/python3
# -*- coding: utf-8 -*-

import os

from webui.app import create_app


if __name__ == "__main__":
    app = create_app()
    host = os.environ.get("CMSEEK_WEBUI_HOST", "127.0.0.1")
    port = int(os.environ.get("CMSEEK_WEBUI_PORT", "5000"))
    debug = os.environ.get("CMSEEK_WEBUI_DEBUG", "0") == "1"
    app.run(host=host, port=port, debug=debug)

