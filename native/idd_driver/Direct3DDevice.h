#pragma once

#include "../capture/dxgi_compat.h"

using Microsoft::WRL::ComPtr;

namespace DualDesk::Driver {

class Direct3DDevice {
public:
    Direct3DDevice();
    ~Direct3DDevice();

    bool Initialize();
    ID3D11Device* GetDevice() const { return m_device.Get(); }
    ID3D11DeviceContext* GetContext() const { return m_context.Get(); }

private:
    ComPtr<ID3D11Device> m_device;
    ComPtr<ID3D11DeviceContext> m_context;
};

} // namespace DualDesk::Driver
