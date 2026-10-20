#include "dxgi_capture.h"

namespace DualDesk::Capture {

DXGICapture::DXGICapture() = default;

DXGICapture::~DXGICapture() {
    Cleanup();
}

bool DXGICapture::Initialize(uint32_t output_index) {
    m_output_index = output_index;
    D3D_FEATURE_LEVEL feature_levels[] = {
        D3D_FEATURE_LEVEL_11_1,
        D3D_FEATURE_LEVEL_11_0,
    };
    D3D_FEATURE_LEVEL selected_level;

    HRESULT hr = D3D11CreateDevice(
        nullptr,
        D3D_DRIVER_TYPE_HARDWARE,
        nullptr,
        D3D11_CREATE_DEVICE_BGRA_SUPPORT,
        feature_levels,
        static_cast<unsigned int>(ARRAYSIZE(feature_levels)),
        D3D11_SDK_VERSION,
        &m_d3d_device,
        &selected_level,
        &m_d3d_context
    );

    if (FAILED(hr)) {
        return false;
    }

    ComPtr<IDXGIDevice> dxgi_device;
    hr = m_d3d_device.As(&dxgi_device);
    if (FAILED(hr)) return false;

    ComPtr<IDXGIAdapter> dxgi_adapter;
    hr = dxgi_device->GetAdapter(reinterpret_cast<void**>(dxgi_adapter.GetAddressOf()));
    if (FAILED(hr)) return false;

    ComPtr<IDXGIOutput> dxgi_output;
    hr = dxgi_adapter->EnumOutputs(output_index, reinterpret_cast<void**>(dxgi_output.GetAddressOf()));
    if (FAILED(hr)) return false;

    ComPtr<IDXGIOutput1> dxgi_output1;
    hr = dxgi_output.As(&dxgi_output1);
    if (FAILED(hr)) return false;

    hr = dxgi_output1->DuplicateOutput(
        m_d3d_device.Get(),
        reinterpret_cast<void**>(m_output_duplication.GetAddressOf())
    );
    if (FAILED(hr)) return false;

    m_initialized = true;
    return true;
}

bool DXGICapture::AcquireNextFrame(FrameInfo& out_frame, uint32_t timeout_ms) {
    if (!m_initialized || !m_output_duplication) return false;

    DXGI_OUTDUPL_FRAME_INFO frame_info{};
    ComPtr<IDXGIResource> desktop_resource;

    HRESULT hr = m_output_duplication->AcquireNextFrame(
        timeout_ms,
        &frame_info,
        reinterpret_cast<void**>(desktop_resource.GetAddressOf())
    );

    if (FAILED(hr)) {
        return false;
    }

    ComPtr<ID3D11Texture2D> desktop_texture;
    hr = desktop_resource.As(&desktop_texture);
    if (FAILED(hr)) {
        m_output_duplication->ReleaseFrame();
        return false;
    }

    D3D11_TEXTURE2D_DESC desc{};
    desktop_texture->GetDesc(&desc);

    out_frame.width = desc.Width;
    out_frame.height = desc.Height;
    out_frame.timestamp_us = static_cast<uint64_t>(frame_info.LastPresentTime.QuadPart);

    m_output_duplication->ReleaseFrame();
    return true;
}

void DXGICapture::ReleaseFrame() {
    if (m_output_duplication) {
        m_output_duplication->ReleaseFrame();
    }
}

void DXGICapture::Cleanup() {
    m_staging_texture.Reset();
    m_output_duplication.Reset();
    m_d3d_context.Reset();
    m_d3d_device.Reset();
    m_initialized = false;
}

} // namespace DualDesk::Capture
