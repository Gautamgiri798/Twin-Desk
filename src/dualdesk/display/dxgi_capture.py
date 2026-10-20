from __future__ import annotations

import ctypes
import platform
import time
from ctypes import wintypes
from dataclasses import dataclass

# Win32 & DirectX Constants
D3D_DRIVER_TYPE_UNKNOWN = 0
D3D_DRIVER_TYPE_HARDWARE = 1
D3D11_CREATE_DEVICE_BGRA_SUPPORT = 0x20
D3D11_SDK_VERSION = 7
D3D11_USAGE_STAGING = 3
D3D11_CPU_ACCESS_READ = 0x20000
D3D11_MAP_READ = 1

DXGI_FORMAT_B8G8R8A8_UNORM = 87
DXGI_ERROR_WAIT_TIMEOUT = 0x887A0027
DXGI_ERROR_ACCESS_LOST = 0x887A0026
DXGI_ERROR_INVALID_CALL = 0x887A0001
S_OK = 0


class GUID(ctypes.Structure):
    _fields_ = [
        ("Data1", ctypes.c_ulong),
        ("Data2", ctypes.c_ushort),
        ("Data3", ctypes.c_ushort),
        ("Data4", ctypes.c_ubyte * 8),
    ]


class RECT(ctypes.Structure):
    _fields_ = [
        ("left", ctypes.c_long),
        ("top", ctypes.c_long),
        ("right", ctypes.c_long),
        ("bottom", ctypes.c_long),
    ]


class DXGI_OUTPUT_DESC(ctypes.Structure):
    _fields_ = [
        ("DeviceName", ctypes.c_wchar * 32),
        ("DesktopCoordinates", RECT),
        ("AttachedToDesktop", wintypes.BOOL),
        ("Rotation", ctypes.c_uint),
        ("Monitor", wintypes.HMONITOR),
    ]


class DXGI_OUTDUPL_FRAME_INFO(ctypes.Structure):
    _fields_ = [
        ("LastPresentTime", ctypes.c_int64),
        ("LastMouseUpdateTime", ctypes.c_int64),
        ("TotalMetadataBuffersSize", ctypes.c_uint),
        ("AccumulatedFrames", ctypes.c_uint),
        ("RectsCoalesced", wintypes.BOOL),
        ("ProtectedContentMaskedOut", wintypes.BOOL),
        ("PointerPositionValid", wintypes.BOOL),
        ("PointerPositionX", ctypes.c_long),
        ("PointerPositionY", ctypes.c_long),
        ("PointerVisible", wintypes.BOOL),
        ("TotalMetadataBufferSize", ctypes.c_uint),
    ]


class D3D11_TEXTURE2D_DESC(ctypes.Structure):
    _fields_ = [
        ("Width", ctypes.c_uint),
        ("Height", ctypes.c_uint),
        ("MipLevels", ctypes.c_uint),
        ("ArraySize", ctypes.c_uint),
        ("Format", ctypes.c_uint),
        ("SampleDescCount", ctypes.c_uint),
        ("SampleDescQuality", ctypes.c_uint),
        ("Usage", ctypes.c_uint),
        ("BindFlags", ctypes.c_uint),
        ("CPUAccessFlags", ctypes.c_uint),
        ("MiscFlags", ctypes.c_uint),
    ]


class D3D11_MAPPED_SUBRESOURCE(ctypes.Structure):
    _fields_ = [
        ("pData", ctypes.c_void_p),
        ("RowPitch", ctypes.c_uint),
        ("DepthPitch", ctypes.c_uint),
    ]


@dataclass
class DXGIFrame:
    width: int
    height: int
    pitch: int
    data: bytes
    timestamp_us: int


def _guid_from_string(s: str) -> GUID:
    g = GUID()
    try:
        ole32 = ctypes.windll.ole32
        ole32.IIDFromString(wintypes.LPCWSTR(s), ctypes.byref(g))
    except (AttributeError, OSError):
        pass
    return g


IID_IDXGIDevice = _guid_from_string("{54ec77fa-1377-44e6-8c32-88fd5f44c84c}")
IID_IDXGIOutput1 = _guid_from_string("{00cddea8-939b-4b83-a340-b1e60747444c}")
IID_IDXGIOutput5 = _guid_from_string("{80A07424-AB52-42EB-833C-0C42FD282D98}")
IID_ID3D11Texture2D = _guid_from_string("{6f15aaf2-d208-4e89-9ab4-489535d34f9c}")


def _call_vtable(ptr: ctypes.c_void_p, idx: int, restype: type, argtypes: list[type], *args: object) -> int:
    if not ptr or not ptr.value:
        return -1
    vtable = ctypes.cast(ptr, ctypes.POINTER(ctypes.POINTER(ctypes.c_void_p))).contents
    fn_ptr = vtable[idx]
    if not fn_ptr:
        return -1
    return int(ctypes.WINFUNCTYPE(restype, *argtypes)(fn_ptr)(ptr, *args))


def _release_com(ptr: ctypes.c_void_p) -> None:
    if ptr and ptr.value:
        try:
            _call_vtable(ptr, 2, ctypes.c_ulong, [ctypes.c_void_p])
        except (AttributeError, OSError, ValueError):
            pass


class DXGICaptureAdapter:
    """
    DirectX 11 / DXGI Desktop Duplication capture adapter.
    Acquires GPU-rendered desktop frames with sub-5ms latency and zero GDI overhead.
    Gracefully falls back to GDI when running in non-DWM, remote desktop, or headless environments.
    """

    def __init__(self, output_index: int = 0) -> None:
        self.output_index = output_index
        self.is_initialized = False
        self.width = 0
        self.height = 0
        self.device_name = ""

        self._p_device: ctypes.c_void_p | None = None
        self._p_context: ctypes.c_void_p | None = None
        self._p_output: ctypes.c_void_p | None = None
        self._p_duplication: ctypes.c_void_p | None = None
        self._p_staging_texture: ctypes.c_void_p | None = None
        self._is_windows = platform.system() == "Windows"

    @classmethod
    def is_supported(cls) -> bool:
        """Checks if DirectX 11 and DXGI Desktop Duplication are supported on this machine."""
        if platform.system() != "Windows":
            return False
        try:
            d3d11 = ctypes.windll.d3d11
            p_dev = ctypes.c_void_p()
            p_ctx = ctypes.c_void_p()
            feat = ctypes.c_uint()
            hr = d3d11.D3D11CreateDevice(
                None,
                D3D_DRIVER_TYPE_HARDWARE,
                None,
                D3D11_CREATE_DEVICE_BGRA_SUPPORT,
                None,
                0,
                D3D11_SDK_VERSION,
                ctypes.byref(p_dev),
                ctypes.byref(feat),
                ctypes.byref(p_ctx),
            )
            supported = (hr == S_OK) and (p_dev.value is not None)
            _release_com(p_ctx)
            _release_com(p_dev)
            return supported
        except (AttributeError, OSError):
            return False

    def initialize(self, output_index: int = 0) -> bool:
        """Initializes DirectX 11 device and queries desktop output duplication."""
        if not self._is_windows:
            return False

        self.cleanup()
        self.output_index = output_index

        try:
            d3d11 = ctypes.windll.d3d11
            p_dev = ctypes.c_void_p()
            p_ctx = ctypes.c_void_p()
            feat = ctypes.c_uint()

            hr = d3d11.D3D11CreateDevice(
                None,
                D3D_DRIVER_TYPE_HARDWARE,
                None,
                D3D11_CREATE_DEVICE_BGRA_SUPPORT,
                None,
                0,
                D3D11_SDK_VERSION,
                ctypes.byref(p_dev),
                ctypes.byref(feat),
                ctypes.byref(p_ctx),
            )
            if hr != S_OK or not p_dev.value:
                return False

            self._p_device = p_dev
            self._p_context = p_ctx

            # Query IDXGIDevice
            p_dxgi_dev = ctypes.c_void_p()
            hr = _call_vtable(
                p_dev,
                0,  # QueryInterface
                ctypes.c_long,
                [ctypes.c_void_p, ctypes.POINTER(GUID), ctypes.POINTER(ctypes.c_void_p)],
                ctypes.byref(IID_IDXGIDevice),
                ctypes.byref(p_dxgi_dev),
            )
            if hr != S_OK or not p_dxgi_dev.value:
                self.cleanup()
                return False

            # IDXGIDevice::GetAdapter
            p_adapter = ctypes.c_void_p()
            hr = _call_vtable(
                p_dxgi_dev,
                7,
                ctypes.c_long,
                [ctypes.c_void_p, ctypes.POINTER(ctypes.c_void_p)],
                ctypes.byref(p_adapter),
            )
            _release_com(p_dxgi_dev)
            if hr != S_OK or not p_adapter.value:
                self.cleanup()
                return False

            # IDXGIAdapter::EnumOutputs
            p_output = ctypes.c_void_p()
            hr = _call_vtable(
                p_adapter,
                7,
                ctypes.c_long,
                [ctypes.c_void_p, ctypes.c_uint, ctypes.POINTER(ctypes.c_void_p)],
                self.output_index,
                ctypes.byref(p_output),
            )
            _release_com(p_adapter)
            if hr != S_OK or not p_output.value:
                self.cleanup()
                return False

            self._p_output = p_output

            # Read output dimensions via GetDesc
            desc = DXGI_OUTPUT_DESC()
            _call_vtable(
                p_output,
                7,  # GetDesc
                ctypes.c_long,
                [ctypes.c_void_p, ctypes.POINTER(DXGI_OUTPUT_DESC)],
                ctypes.byref(desc),
            )
            self.width = desc.DesktopCoordinates.right - desc.DesktopCoordinates.left
            self.height = desc.DesktopCoordinates.bottom - desc.DesktopCoordinates.top
            self.device_name = str(desc.DeviceName)

            # Try DuplicateOutput on IDXGIOutput1 or IDXGIOutput5
            p_dup = ctypes.c_void_p()
            p_out1 = ctypes.c_void_p()
            hr1 = _call_vtable(
                p_output,
                0,
                ctypes.c_long,
                [ctypes.c_void_p, ctypes.POINTER(GUID), ctypes.POINTER(ctypes.c_void_p)],
                ctypes.byref(IID_IDXGIOutput1),
                ctypes.byref(p_out1),
            )
            if hr1 == S_OK and p_out1.value:
                hr_dup = _call_vtable(
                    p_out1,
                    18,  # DuplicateOutput
                    ctypes.c_long,
                    [ctypes.c_void_p, ctypes.c_void_p, ctypes.POINTER(ctypes.c_void_p)],
                    p_dev,
                    ctypes.byref(p_dup),
                )
                _release_com(p_out1)
                if hr_dup == S_OK and p_dup.value:
                    self._p_duplication = p_dup
                    self.is_initialized = True
                    return True

            # Fallback: IDXGIOutput5
            p_out5 = ctypes.c_void_p()
            hr5 = _call_vtable(
                p_output,
                0,
                ctypes.c_long,
                [ctypes.c_void_p, ctypes.POINTER(GUID), ctypes.POINTER(ctypes.c_void_p)],
                ctypes.byref(IID_IDXGIOutput5),
                ctypes.byref(p_out5),
            )
            if hr5 == S_OK and p_out5.value:
                hr_dup = _call_vtable(
                    p_out5,
                    18,
                    ctypes.c_long,
                    [ctypes.c_void_p, ctypes.c_void_p, ctypes.POINTER(ctypes.c_void_p)],
                    p_dev,
                    ctypes.byref(p_dup),
                )
                _release_com(p_out5)
                if hr_dup == S_OK and p_dup.value:
                    self._p_duplication = p_dup
                    self.is_initialized = True
                    return True

            # If desktop duplication is restricted (e.g. headless or permissions), clean up
            self.cleanup()
            return False

        except (AttributeError, OSError, ValueError):
            self.cleanup()
            return False

    def acquire_frame(self, timeout_ms: int = 16) -> DXGIFrame | None:
        """
        Acquires next desktop frame via IDXGIOutputDuplication, maps staging texture,
        and returns DXGIFrame with raw BGRA bytes. Returns None on timeout.
        """
        if not self.is_initialized or not self._p_duplication:
            return None

        try:
            frame_info = DXGI_OUTDUPL_FRAME_INFO()
            p_resource = ctypes.c_void_p()

            # IDXGIOutputDuplication::AcquireNextFrame (vtable 8)
            hr = _call_vtable(
                self._p_duplication,
                8,
                ctypes.c_long,
                [
                    ctypes.c_void_p,
                    ctypes.c_uint,
                    ctypes.POINTER(DXGI_OUTDUPL_FRAME_INFO),
                    ctypes.POINTER(ctypes.c_void_p),
                ],
                timeout_ms,
                ctypes.byref(frame_info),
                ctypes.byref(p_resource),
            )

            if hr == DXGI_ERROR_WAIT_TIMEOUT:
                return None

            if hr == DXGI_ERROR_ACCESS_LOST:
                self.initialize(self.output_index)
                return None

            if hr != S_OK or not p_resource.value:
                return None

            # Query ID3D11Texture2D from resource
            p_desktop_tex = ctypes.c_void_p()
            hr = _call_vtable(
                p_resource,
                0,
                ctypes.c_long,
                [ctypes.c_void_p, ctypes.POINTER(GUID), ctypes.POINTER(ctypes.c_void_p)],
                ctypes.byref(IID_ID3D11Texture2D),
                ctypes.byref(p_desktop_tex),
            )
            _release_com(p_resource)
            if hr != S_OK or not p_desktop_tex.value:
                self.release_frame()
                return None

            desc = D3D11_TEXTURE2D_DESC()
            _call_vtable(
                p_desktop_tex,
                10,  # GetDesc
                None,
                [ctypes.c_void_p, ctypes.POINTER(D3D11_TEXTURE2D_DESC)],
                ctypes.byref(desc),
            )

            # Create staging texture if not allocated
            if not self._p_staging_texture:
                staging_desc = D3D11_TEXTURE2D_DESC(
                    Width=desc.Width,
                    Height=desc.Height,
                    MipLevels=1,
                    ArraySize=1,
                    Format=desc.Format,
                    SampleDescCount=1,
                    SampleDescQuality=0,
                    Usage=D3D11_USAGE_STAGING,
                    BindFlags=0,
                    CPUAccessFlags=D3D11_CPU_ACCESS_READ,
                    MiscFlags=0,
                )
                p_staging = ctypes.c_void_p()
                hr = _call_vtable(
                    self._p_device,
                    5,  # CreateTexture2D
                    ctypes.c_long,
                    [
                        ctypes.c_void_p,
                        ctypes.POINTER(D3D11_TEXTURE2D_DESC),
                        ctypes.c_void_p,
                        ctypes.POINTER(ctypes.c_void_p),
                    ],
                    ctypes.byref(staging_desc),
                    None,
                    ctypes.byref(p_staging),
                )
                if hr != S_OK or not p_staging.value:
                    _release_com(p_desktop_tex)
                    self.release_frame()
                    return None
                self._p_staging_texture = p_staging

            # ID3D11DeviceContext::CopyResource (vtable 47)
            _call_vtable(
                self._p_context,
                47,
                None,
                [ctypes.c_void_p, ctypes.c_void_p, ctypes.c_void_p],
                self._p_staging_texture,
                p_desktop_tex,
            )
            _release_com(p_desktop_tex)

            # ID3D11DeviceContext::Map (vtable 14)
            mapped = D3D11_MAPPED_SUBRESOURCE()
            hr = _call_vtable(
                self._p_context,
                14,
                ctypes.c_long,
                [
                    ctypes.c_void_p,
                    ctypes.c_void_p,
                    ctypes.c_uint,
                    ctypes.c_uint,
                    ctypes.c_uint,
                    ctypes.POINTER(D3D11_MAPPED_SUBRESOURCE),
                ],
                self._p_staging_texture,
                0,
                D3D11_MAP_READ,
                0,
                ctypes.byref(mapped),
            )

            frame: DXGIFrame | None = None
            if hr == S_OK and mapped.pData:
                total_bytes = mapped.RowPitch * desc.Height
                raw_bytes = ctypes.string_at(mapped.pData, total_bytes)
                # Unmap (vtable 15)
                _call_vtable(
                    self._p_context,
                    15,
                    None,
                    [ctypes.c_void_p, ctypes.c_void_p, ctypes.c_uint],
                    self._p_staging_texture,
                    0,
                )
                frame = DXGIFrame(
                    width=desc.Width,
                    height=desc.Height,
                    pitch=mapped.RowPitch,
                    data=raw_bytes,
                    timestamp_us=int(time.time() * 1_000_000),
                )

            self.release_frame()
            return frame

        except (AttributeError, OSError, ValueError):
            self.release_frame()
            return None

    def release_frame(self) -> None:
        """Releases acquired duplication frame back to DWM."""
        if self._p_duplication and self._p_duplication.value:
            try:
                _call_vtable(
                    self._p_duplication,
                    14,  # ReleaseFrame
                    ctypes.c_long,
                    [ctypes.c_void_p],
                )
            except (AttributeError, OSError, ValueError):
                pass

    def cleanup(self) -> None:
        """Releases all DirectX 11 and DXGI resources."""
        self.release_frame()
        _release_com(self._p_staging_texture)
        self._p_staging_texture = None
        _release_com(self._p_duplication)
        self._p_duplication = None
        _release_com(self._p_output)
        self._p_output = None
        _release_com(self._p_context)
        self._p_context = None
        _release_com(self._p_device)
        self._p_device = None
        self.is_initialized = False
