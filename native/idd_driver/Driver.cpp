#include "Driver.h"
#include "VirtualMonitor.h"

extern "C" NTSTATUS DriverEntry(
    _In_ PDRIVER_OBJECT DriverObject,
    _In_ PUNICODE_STRING RegistryPath
) {
    WDF_DRIVER_CONFIG config{};
    WDF_DRIVER_CONFIG_INIT(&config, EvtDeviceAdd);

    NTSTATUS status = WdfDriverCreate(
        DriverObject,
        RegistryPath,
        WDF_NO_OBJECT_ATTRIBUTES,
        &config,
        WDF_NO_HANDLE
    );

    return status;
}

NTSTATUS EvtDeviceAdd(
    _In_ WDFDRIVER Driver,
    _Inout_ PWDFDEVICE_INIT DeviceInit
) {
    UNREFERENCED_PARAMETER(Driver);

    NTSTATUS status = IddCxDeviceInitConfig(DeviceInit, nullptr);
    if (!NT_SUCCESS(status)) {
        return status;
    }

    WDF_OBJECT_ATTRIBUTES attr{};
    WDF_OBJECT_ATTRIBUTES_INIT_CONTEXT_TYPE(&attr, DriverDeviceContext);

    WDFDEVICE device{};
    status = WdfDeviceCreate(&DeviceInit, &attr, &device);
    if (!NT_SUCCESS(status)) {
        return status;
    }

    IDDCX_ADAPTER_CAPS adapterCaps{};
    adapterCaps.Size = sizeof(adapterCaps);
    adapterCaps.MaxMonitorsSupportedByOS = 1;

    IDARG_IN_ADAPTER_INIT adapterInit{};
    adapterInit.WdfDevice = device;
    adapterInit.pCaps = &adapterCaps;

    IDARG_OUT_ADAPTER_INIT adapterOut{};
    status = IddCxAdapterInitAsync(&adapterInit, &adapterOut);
    if (!NT_SUCCESS(status)) {
        return status;
    }

    auto* context = GetDeviceContext(device);
    if (context) {
        context->Adapter = adapterOut.AdapterObject;
        DualDesk::Driver::CreateVirtualMonitor(context->Adapter);
    }

    return STATUS_SUCCESS;
}
