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
    #if __has_include(<cstdint>)
      #define DUALDESK_HAS_CSTDINT 1
      #include <cstdint>
    #endif
    #if __has_include(<vector>)
      #define DUALDESK_HAS_VECTOR 1
      #include <vector>
    #endif
    #if __has_include(<cstring>)
      #define DUALDESK_HAS_CSTRING 1
      #include <cstring>
    #endif
  #endif
#endif

#ifndef DUALDESK_HAS_CSTDINT
  typedef unsigned int uint32_t;
  typedef unsigned long long uint64_t;
  typedef unsigned char uint8_t;
  typedef unsigned long long size_t;
#endif

#ifndef DUALDESK_HAS_VECTOR
namespace std {
  template <typename T>
  class vector {
      T* data_{ nullptr };
      size_t size_{ 0 };
  public:
      vector() = default;
      ~vector() { delete[] data_; }
      void resize(size_t s) {
          delete[] data_;
          size_ = s;
          data_ = s > 0 ? new T[s] : nullptr;
      }
      size_t size() const { return size_; }
      T* data() { return data_; }
      const T* data() const { return data_; }
  };
}
#endif

#ifndef DUALDESK_HAS_CSTRING
namespace std {
  inline void* memcpy(void* d, const void* s, size_t n) {
      char* cd = static_cast<char*>(d);
      const char* cs = static_cast<const char*>(s);
      for (size_t i = 0; i < n; ++i) cd[i] = cs[i];
      return d;
  }
}
#endif

#ifndef DUALDESK_HAS_WRL
namespace Microsoft {
namespace WRL {
    template <typename T>
    class ComPtr {
        T* ptr_{ nullptr };
    public:
        ComPtr() = default;
        ComPtr(T* p) : ptr_(p) {}
        ~ComPtr() { Reset(); }

        T* Get() const { return ptr_; }
        T** GetAddressOf() { return &ptr_; }
        T** ReleaseAndGetAddressOf() {
            Reset();
            return &ptr_;
        }
        T** operator&() { return &ptr_; }
        T* operator->() const { return ptr_; }
        explicit operator bool() const { return ptr_ != nullptr; }
        void Reset() { ptr_ = nullptr; }

        template <typename U>
        long As(ComPtr<U>* out) {
            if (out) *out = ComPtr<U>(reinterpret_cast<U*>(ptr_));
            return 0;
        }

        template <typename U>
        long As(U** out) {
            if (out) *out = reinterpret_cast<U*>(ptr_);
            return 0;
        }
    };
} // namespace WRL
} // namespace Microsoft
#endif

#ifndef DUALDESK_HAS_D3D11
enum D3D_FEATURE_LEVEL {
    D3D_FEATURE_LEVEL_11_0 = 0xb000,
    D3D_FEATURE_LEVEL_11_1 = 0xb100,
};

enum D3D_DRIVER_TYPE {
    D3D_DRIVER_TYPE_HARDWARE = 1,
};

#define D3D11_CREATE_DEVICE_BGRA_SUPPORT 0x20L
#define D3D11_SDK_VERSION 7
#define D3D11_USAGE_STAGING 3
#define D3D11_CPU_ACCESS_READ 0x20000L
#define D3D11_MAP_READ 1

struct D3D11_TEXTURE2D_DESC {
    unsigned int Width{ 1920 };
    unsigned int Height{ 1080 };
    unsigned int MipLevels{ 1 };
    unsigned int ArraySize{ 1 };
    unsigned int Format{ 87 };
    unsigned int SampleDescCount{ 1 };
    unsigned int SampleDescQuality{ 0 };
    unsigned int Usage{ 0 };
    unsigned int BindFlags{ 0 };
    unsigned int CPUAccessFlags{ 0 };
    unsigned int MiscFlags{ 0 };
};

struct D3D11_MAPPED_SUBRESOURCE {
    void* pData{ nullptr };
    unsigned int RowPitch{ 0 };
    unsigned int DepthPitch{ 0 };
};

struct ID3D11Resource {
    virtual ~ID3D11Resource() = default;
};

struct ID3D11Texture2D : public ID3D11Resource {
    void GetDesc(D3D11_TEXTURE2D_DESC* pDesc) {
        if (pDesc) {
            pDesc->Width = 1920;
            pDesc->Height = 1080;
        }
    }
};

struct ID3D11Device {
    template <typename T>
    long As(Microsoft::WRL::ComPtr<T>* out) {
        if (out) *out = Microsoft::WRL::ComPtr<T>(reinterpret_cast<T*>(this));
        return 0;
    }
    long CreateTexture2D(const D3D11_TEXTURE2D_DESC*, void*, ID3D11Texture2D** ppTexture) {
        if (ppTexture) *ppTexture = reinterpret_cast<ID3D11Texture2D*>(0x10);
        return 0;
    }
};

struct ID3D11DeviceContext {
    void Reset() {}
    void CopyResource(ID3D11Resource*, ID3D11Resource*) {}
    long Map(ID3D11Resource*, unsigned int, unsigned int, unsigned int, D3D11_MAPPED_SUBRESOURCE*) { return 0; }
    void Unmap(ID3D11Resource*, unsigned int) {}
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
