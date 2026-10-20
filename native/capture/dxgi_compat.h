#pragma once

// DirectX 11 & DXGI Compatibility Header
// Includes official Windows SDK DirectX headers when present,
// and provides clean interface definitions for IntelliSense when SDK paths are not configured.

#if defined(_WIN32)
  #if defined(__has_include)
    #if __has_include(<windows.h>)
      #include <windows.h>
    #endif
    #if __has_include(<d3d11.h>)
      #define DUALDESK_HAS_D3D11 1
      #include <d3d11.h>
    #endif
    #if __has_include(<dxgi1_2.h>)
      #define DUALDESK_HAS_DXGI 1
      #include <dxgi1_2.h>
    #endif
    #if __has_include(<wrl/client.h>)
      #define DUALDESK_HAS_WRL 1
      #include <wrl/client.h>
    #endif
  #endif
#endif

#ifndef DUALDESK_HAS_WRL
namespace Microsoft::WRL {
    template <typename T>
    class ComPtr {
        T* ptr_{ nullptr };
    public:
        ComPtr() = default;
        ComPtr(T* p) : ptr_(p) {}
        ~ComPtr() { Reset(); }

        T* Get() const { return ptr_; }
        T** GetAddressOf() { return &ptr_; }
        T** operator&() { return &ptr_; }
        T* operator->() const { return ptr_; }
        explicit operator bool() const { return ptr_ != nullptr; }
        void Reset() { ptr_ = nullptr; }

        template <typename U>
        long As(ComPtr<U>* out) {
            if (out) *out = ComPtr<U>(reinterpret_cast<U*>(ptr_));
            return 0;
        }
    };
}
#endif

#ifndef DUALDESK_HAS_D3D11
struct ID3D11Device {
    template <typename T>
    long As(Microsoft::WRL::ComPtr<T>* out) {
        if (out) *out = Microsoft::WRL::ComPtr<T>(reinterpret_cast<T*>(this));
        return 0;
    }
};
struct ID3D11DeviceContext {
    void Reset() {}
};
struct ID3D11Texture2D {
    void GetDesc(void*) {}
};
struct IDXGIResource {
    template <typename T>
    long As(Microsoft::WRL::ComPtr<T>* out) {
        if (out) *out = Microsoft::WRL::ComPtr<T>(reinterpret_cast<T*>(this));
        return 0;
    }
};
struct IDXGIAdapter {
    long EnumOutputs(unsigned int, void**) { return 0; }
};
struct IDXGIDevice {
    long GetAdapter(void**) { return 0; }
};
struct IDXGIOutput {
    template <typename T>
    long As(Microsoft::WRL::ComPtr<T>* out) {
        if (out) *out = Microsoft::WRL::ComPtr<T>(reinterpret_cast<T*>(this));
        return 0;
    }
};
struct IDXGIOutput1 {
    long DuplicateOutput(ID3D11Device*, void**) { return 0; }
};
struct IDXGIOutputDuplication {
    long AcquireNextFrame(unsigned int, void*, void**) { return 0; }
    void ReleaseFrame() {}
};

typedef long HRESULT;
#define S_OK ((HRESULT)0L)
#define SUCCEEDED(hr) (((HRESULT)(hr)) >= 0)
#define FAILED(hr) (((HRESULT)(hr)) < 0)
#define ARRAYSIZE(A) (sizeof(A)/sizeof((A)[0]))

enum D3D_FEATURE_LEVEL {
    D3D_FEATURE_LEVEL_11_0 = 0xb000,
    D3D_FEATURE_LEVEL_11_1 = 0xb100,
};

enum D3D_DRIVER_TYPE {
    D3D_DRIVER_TYPE_HARDWARE = 1,
};

#define D3D11_CREATE_DEVICE_BGRA_SUPPORT 0x20L
#define D3D11_SDK_VERSION 7

struct D3D11_TEXTURE2D_DESC {
    unsigned int Width{ 1920 };
    unsigned int Height{ 1080 };
};

struct DXGI_OUTDUPL_FRAME_INFO {
    union {
        long long QuadPart{ 0 };
    } LastPresentTime;
};

inline HRESULT D3D11CreateDevice(
    void*, D3D_DRIVER_TYPE, void*, unsigned int,
    const D3D_FEATURE_LEVEL*, unsigned int, unsigned int,
    ID3D11Device** ppDevice, D3D_FEATURE_LEVEL* pFeatureLevel,
    ID3D11DeviceContext** ppImmediateContext
) {
    if (ppDevice) *ppDevice = reinterpret_cast<ID3D11Device*>(0x1);
    if (ppImmediateContext) *ppImmediateContext = reinterpret_cast<ID3D11DeviceContext*>(0x2);
    if (pFeatureLevel) *pFeatureLevel = D3D_FEATURE_LEVEL_11_1;
    return S_OK;
}
#endif
