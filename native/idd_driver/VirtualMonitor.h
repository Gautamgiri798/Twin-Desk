#pragma once

#include "idd_compat.h"

namespace DualDesk::Driver {

NTSTATUS CreateVirtualMonitor(IDDCX_ADAPTER adapter);

extern "C" {
    NTSTATUS EvtMonitorQueryTargetModes(
        IDDCX_MONITOR MonitorObject,
        const IDARG_IN_QUERYTARGETMODES* pInArgs,
        IDARG_OUT_QUERYTARGETMODES* pOutArgs
    );
    NTSTATUS EvtMonitorAssignSwapChain(
        IDDCX_MONITOR MonitorObject,
        const IDARG_IN_SETSWAPCHAIN* pInArgs
    );
    NTSTATUS EvtMonitorUnassignSwapChain(
        IDDCX_MONITOR MonitorObject
    );
}

} // namespace DualDesk::Driver
