#pragma once

#include <cstdint>
#include <vector>
#include <memory>
#include "dxgi_compat.h"

using Microsoft::WRL::ComPtr;

namespace DualDesk::Capture {

struct FrameInfo {
    uint32_t width{ 0 };
    uint32_t height{ 0 };
    uint32_t pitch{ 0 };
    uint64_t timestamp_us{ 0 };
    std::vector<uint8_t> buffer;
};

class DXGICapture {
public:
    DXGICapture();
    ~DXGICapture();

    bool Initialize(uint32_t output_index = 0);
    bool AcquireNextFrame(FrameInfo& out_frame, uint32_t timeout_ms = 16);
    void ReleaseFrame();
    void Cleanup();

    bool IsInitialized() const { return m_initialized; }

private:
    bool m_initialized{ false };
    uint32_t m_output_index{ 0 };

    ComPtr<ID3D11Device> m_d3d_device;
    ComPtr<ID3D11DeviceContext> m_d3d_context;
    ComPtr<IDXGIOutputDuplication> m_output_duplication;
    ComPtr<ID3D11Texture2D> m_staging_texture;
};

} // namespace DualDesk::Capture
