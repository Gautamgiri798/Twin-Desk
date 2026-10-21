#pragma once

#include "idd_compat.h"

extern "C" {
    NTSTATUS DriverEntry(
        _In_ PDRIVER_OBJECT DriverObject,
        _In_ PUNICODE_STRING RegistryPath
    );
    NTSTATUS EvtDeviceAdd(
        _In_ WDFDRIVER Driver,
        _Inout_ PWDFDEVICE_INIT DeviceInit
    );
}

struct DriverDeviceContext {
    IDDCX_ADAPTER Adapter;
};

WDF_DECLARE_CONTEXT_TYPE_WITH_NAME(DriverDeviceContext, GetDeviceContext);
