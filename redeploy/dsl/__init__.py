"""redeploy CSS-like DSL — parser, loader, exporter.

Format: ``redeploy.css`` (or ``redeploy.less``)

    @app c2004;

    environment[name="prod"] {
      host: root@87.106.87.183;
      strategy: docker_full;
    }

    template[id="rpi-kiosk"] {
      score[is_arm]: 2.0;
      score[no_docker]: 2.0;
      score[chromium]: 2.0;
      environment: kiosk;
      strategy: native_kiosk;
      spec: 04-rpi-kiosk/migration-rpi5.yaml;
    }

    workflow[name="deploy:prod"] {
      trigger: manual;
      step-1: redeploy run --env prod --detect;
      step-2: redeploy run --env prod;
    }
"""
from .parser import RedeployDSLParser, DSLNode
from .loader import load_css

__all__ = ["RedeployDSLParser", "DSLNode", "load_css"]
