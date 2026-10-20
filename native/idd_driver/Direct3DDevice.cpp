#include "Direct3DDevice.h"

namespace DualDesk::Driver {

Direct3DDevice::Direct3DDevice() = default;
Direct3DDevice::~Direct3DDevice() = default;

bool Direct3DDevice::Initialize() {
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
        &m_device,
        &selected_level,
        &m_context
    );

    return SUCCEEDED(hr);
}

} // namespace DualDesk::Driver
