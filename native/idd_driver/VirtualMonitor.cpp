#include "VirtualMonitor.h"
#include "Direct3DDevice.h"

namespace DualDesk::Driver {

// Standard EDID block reporting 1080p and 1440p support
static const BYTE s_VirtualMonitorEdidBlock[128] = {
    0x00, 0xFF, 0xFF, 0xFF, 0xFF, 0xFF, 0xFF, 0x00, // Header
    0x14, 0x0A, 0x01, 0x00, 0x01, 0x01, 0x01, 0x01, // Manufacturer DualDesk ID
    0x01, 0x21, 0x01, 0x04, 0xA5, 0x34, 0x20, 0x78, // EDID structure version 1.4
    0x3B, 0xEE, 0x91, 0xA3, 0x54, 0x4C, 0x99, 0x26, 
    0x0F, 0x50, 0x54, 0x21, 0x08, 0x00, 0xD1, 0xC0, 
    0x81, 0xC0, 0x81, 0x00, 0x95, 0x00, 0xB3, 0x00, 
    0x01, 0x01, 0x01, 0x01, 0x01, 0x01, 0x02, 0x3A, 
    0x80, 0x18, 0x71, 0x38, 0x2D, 0x40, 0x58, 0x2C, // 1920x1080@60Hz detailed timing descriptor
    0x45, 0x00, 0x09, 0x25, 0x21, 0x00, 0x00, 0x1E, 
    0x00, 0x00, 0x00, 0xFC, 0x00, 0x44, 0x75, 0x61, 
    0x6C, 0x44, 0x65, 0x73, 0x6B, 0x20, 0x56, 0x4D, 
    0x6F, 0x6E, 0x00, 0x00, 0x00, 0xFD, 0x00, 0x38, 
    0x4C, 0x1E, 0x53, 0x11, 0x00, 0x0A, 0x20, 0x20, 
    0x20, 0x20, 0x20, 0x20, 0x00, 0x00, 0x00, 0x10, 
    0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 
    0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x17  // Checksum
};

NTSTATUS CreateVirtualMonitor(IDDCX_ADAPTER adapter) {
    IDDCX_MONITOR_INFO monitorInfo{};
    monitorInfo.Size = sizeof(monitorInfo);
    monitorInfo.MonitorType = DISPLAYCONFIG_OUTPUT_TECHNOLOGY_DISPLAYPORT_EMBEDDED;
    monitorInfo.ConnectorIndex = 0;

    IDDCX_MONITOR_DESCRIPTION monitorDesc{};
    monitorDesc.Size = sizeof(monitorDesc);
    monitorDesc.Type = IDDCX_MONITOR_DESCRIPTION_TYPE_EDID;
    monitorDesc.DataSize = sizeof(s_VirtualMonitorEdidBlock);
    monitorDesc.pData = const_cast<BYTE*>(s_VirtualMonitorEdidBlock);

    monitorInfo.pMonitorDescription = &monitorDesc;

    IDARG_IN_MONITORCREATE monitorCreate{};
    monitorCreate.ObjectAttributes = nullptr;
    monitorCreate.pMonitorInfo = &monitorInfo;

    IDARG_OUT_MONITORCREATE monitorCreateOut{};
    NTSTATUS status = IddCxMonitorCreate(adapter, &monitorCreate, &monitorCreateOut);
    if (!NT_SUCCESS(status)) {
        return status;
    }

    IDARG_IN_MONITORARRIVAL arrival{};
    arrival.MonitorObject = monitorCreateOut.MonitorObject;
    return IddCxMonitorArrival(monitorCreateOut.MonitorObject, &arrival);
}

NTSTATUS EvtMonitorQueryTargetModes(
    _In_ IDDCX_MONITOR MonitorObject,
    _In_ const IDARG_IN_QUERYTARGETMODES* pInArgs,
    _Out_ IDARG_OUT_QUERYTARGETMODES* pOutArgs
) {
    UNREFERENCED_PARAMETER(MonitorObject);
    UNREFERENCED_PARAMETER(pInArgs);
    UNREFERENCED_PARAMETER(pOutArgs);
    return STATUS_SUCCESS;
}

NTSTATUS EvtMonitorAssignSwapChain(
    _In_ IDDCX_MONITOR MonitorObject,
    _In_ const IDARG_IN_SETSWAPCHAIN* pInArgs
) {
    UNREFERENCED_PARAMETER(MonitorObject);
    UNREFERENCED_PARAMETER(pInArgs);
    return STATUS_SUCCESS;
}

NTSTATUS EvtMonitorUnassignSwapChain(
    _In_ IDDCX_MONITOR MonitorObject
) {
    UNREFERENCED_PARAMETER(MonitorObject);
    return STATUS_SUCCESS;
}

} // namespace DualDesk::Driver
