#pragma once

#include "idd_compat.h"

extern "C" {
    NTSTATUS DriverEntry(
        PDRIVER_OBJECT DriverObject,
        PUNICODE_STRING RegistryPath
    );
    NTSTATUS EvtDeviceAdd(
        WDFDRIVER Driver,
        PWDFDEVICE_INIT DeviceInit
    );
}

struct DriverDeviceContext {
    IDDCX_ADAPTER Adapter;
};

WDF_DECLARE_CONTEXT_TYPE_WITH_NAME(DriverDeviceContext, GetDeviceContext);
