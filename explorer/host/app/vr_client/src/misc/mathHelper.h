#pragma once

#include <Eigen/Dense>

Eigen::Matrix4f CreateProjectionMatrix(const float angleLeft, const float angleRight,
                                       const float angleUp, const float angleDown,
                                       const float nearZ, const float farZ)
{
    Eigen::Matrix4f result = Eigen::Matrix4f::Zero();

    const float tanLeft = tanf(angleLeft);
    const float tanRight = tanf(angleRight);

    const float tanDown = tanf(angleUp);
    const float tanUp = tanf(angleDown);

    const float tanAngleWidth = tanRight - tanLeft;
    const float tanAngleHeight = tanUp - tanDown;

    result(0, 0) = 2.0f / tanAngleWidth;
    result(1, 1) = 2.0f / tanAngleHeight;
    result(0, 2) = (tanRight + tanLeft) / tanAngleWidth;
    result(1, 2) = (tanUp + tanDown) / tanAngleHeight;
    result(2, 2) = -(farZ) / (farZ - nearZ);
    result(2, 3) = -(farZ * (nearZ)) / (farZ - nearZ);
    result(3, 2) = -1.0f;

    return result;
}