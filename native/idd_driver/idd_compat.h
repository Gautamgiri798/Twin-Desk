#pragma once

// Windows & WDF / IddCx Compatibility Header
// Allows DualDesk driver files to compile cleanly with the official Windows Driver Kit (WDK)
// while providing complete IntelliSense and IDE static-analysis definitions when opened
// in environments where the WDK has not yet been installed.

#if defined(_WIN32)
  #if defined(__has_include)
    #if __has_include(<windows.h>)
      #include <windows.h>
    #endif
    #if __has_include(<wdf.h>)
      #define DUALDESK_HAS_WDF 1
      #include <wdf.h>
    #endif
    #if __has_include(<iddcx.h>)
      #define DUALDESK_HAS_IDDCX 1
      #include <iddcx.h>
    #endif
  #endif
#endif

#ifndef _WIN32
  #define _In_
  #define _Inout_
  #define _Out_
#endif

#ifndef _In_
  #define _In_
#endif
#ifndef _Inout_
  #define _Inout_
#endif
#ifndef _Out_
  #define _Out_
#endif

#ifndef UNREFERENCED_PARAMETER
  #define UNREFERENCED_PARAMETER(P) (void)(P)
#endif

#ifndef DUALDESK_HAS_WDF
  typedef long NTSTATUS;
  #define STATUS_SUCCESS ((NTSTATUS)0x00000000L)
  #define NT_SUCCESS(Status) (((NTSTATUS)(Status)) >= 0)

  typedef void* PDRIVER_OBJECT;
  typedef void* PUNICODE_STRING;
  typedef void* WDFDRIVER;
  typedef void* WDFDEVICE;
  typedef void* PWDFDEVICE_INIT;
  struct WDF_OBJECT_ATTRIBUTES {
      unsigned long Size;
      void* ExecutionLevel;
      void* SynchronizationScope;
  };
  typedef WDF_OBJECT_ATTRIBUTES* PWDF_OBJECT_ATTRIBUTES;

  typedef void* WDF_NO_HANDLE_TYPE;
  typedef unsigned char BYTE;

  #define WDF_NO_HANDLE ((WDF_NO_HANDLE_TYPE)0)
  #define WDF_NO_OBJECT_ATTRIBUTES ((PWDF_OBJECT_ATTRIBUTES)nullptr)

  typedef NTSTATUS DRIVER_INITIALIZE(PDRIVER_OBJECT, PUNICODE_STRING);
  typedef NTSTATUS EVT_WDF_DRIVER_DEVICE_ADD(WDFDRIVER, PWDFDEVICE_INIT);
  typedef void EVT_WDF_OBJECT_CONTEXT_CLEANUP(void*);
  typedef NTSTATUS EVT_WDF_DEVICE_D0_ENTRY(WDFDEVICE, int);

  struct WDF_DRIVER_CONFIG {
      unsigned long Size;
      EVT_WDF_DRIVER_DEVICE_ADD* EvtDriverDeviceAdd;
  };

  inline void WDF_DRIVER_CONFIG_INIT(WDF_DRIVER_CONFIG* config, EVT_WDF_DRIVER_DEVICE_ADD* evt) {
      if (config) {
          config->Size = sizeof(WDF_DRIVER_CONFIG);
          config->EvtDriverDeviceAdd = evt;
      }
  }

  inline NTSTATUS WdfDriverCreate(
      PDRIVER_OBJECT,
      PUNICODE_STRING,
      PWDF_OBJECT_ATTRIBUTES,
      WDF_DRIVER_CONFIG*,
      void*
  ) {
      return STATUS_SUCCESS;
  }

  #define WDF_OBJECT_ATTRIBUTES_INIT_CONTEXT_TYPE(_attributes, _contextType) \
      do { \
          if ((_attributes) != nullptr) { \
              (_attributes)->Size = sizeof(*(_attributes)); \
          } \
      } while (0)

  inline NTSTATUS WdfDeviceCreate(
      PWDFDEVICE_INIT*,
      PWDF_OBJECT_ATTRIBUTES,
      WDFDEVICE*
  ) {
      return STATUS_SUCCESS;
  }

  #define WDF_DECLARE_CONTEXT_TYPE_WITH_NAME(type, func_name) \
      inline type* func_name(WDFDEVICE) { \
          static type s_context{}; \
          return &s_context; \
      }
#endif

#ifndef DUALDESK_HAS_IDDCX
  typedef void* IDDCX_ADAPTER;
  typedef void* IDDCX_MONITOR;

  struct IDDCX_ADAPTER_CAPS {
      unsigned long Size;
      unsigned int MaxMonitorsSupportedByOS;
  };

  struct IDARG_IN_ADAPTER_INIT {
      WDFDEVICE WdfDevice;
      const IDDCX_ADAPTER_CAPS* pCaps;
  };

  struct IDARG_OUT_ADAPTER_INIT {
      IDDCX_ADAPTER AdapterObject;
  };

  inline NTSTATUS IddCxDeviceInitConfig(PWDFDEVICE_INIT, void*) {
      return STATUS_SUCCESS;
  }

  inline NTSTATUS IddCxAdapterInitAsync(const IDARG_IN_ADAPTER_INIT*, IDARG_OUT_ADAPTER_INIT* pOut) {
      if (pOut) pOut->AdapterObject = reinterpret_cast<IDDCX_ADAPTER>(0x1);
      return STATUS_SUCCESS;
  }

  #ifndef DISPLAYCONFIG_OUTPUT_TECHNOLOGY_DISPLAYPORT_EMBEDDED
    #define DISPLAYCONFIG_OUTPUT_TECHNOLOGY_DISPLAYPORT_EMBEDDED 11
  #endif

  #ifndef IDDCX_MONITOR_DESCRIPTION_TYPE_EDID
    #define IDDCX_MONITOR_DESCRIPTION_TYPE_EDID 1
  #endif

  struct IDDCX_MONITOR_DESCRIPTION {
      unsigned long Size;
      unsigned int Type;
      unsigned int DataSize;
      BYTE* pData;
  };

  struct IDDCX_MONITOR_INFO {
      unsigned long Size;
      unsigned int MonitorType;
      unsigned int ConnectorIndex;
      IDDCX_MONITOR_DESCRIPTION* pMonitorDescription;
  };

  struct IDARG_IN_MONITORCREATE {
      void* ObjectAttributes;
      const IDDCX_MONITOR_INFO* pMonitorInfo;
  };

  struct IDARG_OUT_MONITORCREATE {
      IDDCX_MONITOR MonitorObject;
  };

  struct IDARG_IN_MONITORARRIVAL {
      IDDCX_MONITOR MonitorObject;
  };

  inline NTSTATUS IddCxMonitorCreate(IDDCX_ADAPTER, const IDARG_IN_MONITORCREATE*, IDARG_OUT_MONITORCREATE* pOut) {
      if (pOut) pOut->MonitorObject = reinterpret_cast<IDDCX_MONITOR>(0x2);
      return STATUS_SUCCESS;
  }

  inline NTSTATUS IddCxMonitorArrival(IDDCX_MONITOR, const IDARG_IN_MONITORARRIVAL*) {
      return STATUS_SUCCESS;
  }

  #ifndef DISPLAYCONFIG_RATIONAL
  struct DISPLAYCONFIG_RATIONAL {
      unsigned int Numerator;
      unsigned int Denominator;
  };
  #endif

  #ifndef DISPLAYCONFIG_2DREGION
  struct DISPLAYCONFIG_2DREGION {
      unsigned int cx;
      unsigned int cy;
  };
  #endif

  #ifndef DISPLAYCONFIG_VIDEO_SIGNAL_INFO
  struct DISPLAYCONFIG_VIDEO_SIGNAL_INFO {
      unsigned long long pixelRate;
      DISPLAYCONFIG_RATIONAL hSyncFreq;
      DISPLAYCONFIG_RATIONAL vSyncFreq;
      DISPLAYCONFIG_2DREGION activeSize;
      DISPLAYCONFIG_2DREGION totalSize;
      unsigned int videoStandard;
      unsigned int scanLineOrdering;
  };
  #endif

  #ifndef DISPLAYCONFIG_TARGET_MODE
  struct DISPLAYCONFIG_TARGET_MODE {
      DISPLAYCONFIG_VIDEO_SIGNAL_INFO targetVideoSignalInfo;
  };
  #endif

  struct IDDCX_TARGET_MODE {
      unsigned int Size;
      DISPLAYCONFIG_TARGET_MODE TargetMode;
      unsigned int RequiredBandwidth;
  };

  struct IDARG_IN_QUERYTARGETMODES {
      IDDCX_MONITOR_DESCRIPTION MonitorDescription;
      unsigned int TargetModeBufferInputCount;
      IDDCX_TARGET_MODE* pTargetModes;
  };

  struct IDARG_OUT_QUERYTARGETMODES {
      unsigned int TargetModeBufferOutputCount;
  };

  struct IDARG_IN_SETSWAPCHAIN {};

  typedef NTSTATUS EVT_IDD_CX_MONITOR_QUERY_TARGET_MODES(
      IDDCX_MONITOR, const IDARG_IN_QUERYTARGETMODES*, IDARG_OUT_QUERYTARGETMODES*
  );
  typedef NTSTATUS EVT_IDD_CX_MONITOR_ASSIGN_SWAPCHAIN(
      IDDCX_MONITOR, const IDARG_IN_SETSWAPCHAIN*
  );
  typedef NTSTATUS EVT_IDD_CX_MONITOR_UNASSIGN_SWAPCHAIN(
      IDDCX_MONITOR
  );
#endif
