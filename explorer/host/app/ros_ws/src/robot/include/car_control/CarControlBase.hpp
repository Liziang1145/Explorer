#pragma once

#include <Eigen/Eigen>
#include <Eigen/Core>
#include <Eigen/Dense>
#include <Eigen/Geometry>

namespace WHU_ROBOT{

	constexpr float RAD2DEG = 180.0f / static_cast<float>(M_PI);
	/*
	mode:
	odom:
		0 - no cnt, no vel
		1 - no cnt, has vel
		2- has cnt , no vel
		3 - both has
		|~|~|~|~|	|~|~|cnt|vel|
	target:
		|control enable|~|~|~|	|~|~|cnt|vel|
	control:
		0 - disable
		1 - stop
		2 - free
		6 - 4T4D
		8 - parallel
	*/
	struct CarState{
		uint8_t mode;
		uint32_t cnt;
		uint64_t time;
		Eigen::Vector3f base_pos;
		Eigen::Quaternionf base_quat;
		Eigen::Vector3f base_lin_vel;//m/s, 0.001m/s
		Eigen::Vector3f base_ang_vel;//degree/s, 0.01deg/s
	};

	class CarControllerBase{
	public:
		CarControllerBase() = default;
		virtual ~CarControllerBase() = 0;

		virtual void feedTarget(const CarState& targetState) = 0;
		virtual void feedCurrent(const CarState& currentState) = 0;
		virtual CarState computeControlOnce(void) = 0;
	};

	inline CarControllerBase::~CarControllerBase() { }



	/* @param q   输入四元数 (Eigen::Quaternionf)，假设已归一化
	* @return    一个 Eigen::Vector3f，存放 {roll, pitch, yaw}（弧度）
	*/
	inline Eigen::Vector3f quaternionToEuler(const Eigen::Quaternionf& _q)
	{
		// 确保四元数是归一化的；若有可能未归一化，最好先手动 normalize：
		Eigen::Quaternionf q = _q.normalized();
		const float w = q.w();
		const float x = q.x();
		const float y = q.y();
		const float z = q.z();

		// 计算 sin(pitch) 的中间值，并 clamp 到 [-1, +1]
		float sinp = 2.0f * (w * y - z * x);
		if (sinp > +1.0f) sinp = +1.0f;
		if (sinp < -1.0f) sinp = -1.0f;

		// 逐项计算 roll, pitch, yaw
		float roll  = std::atan2(2.0f * (w * x + y * z),
					1.0f - 2.0f * (x * x + y * y));
		float pitch = std::asin(sinp);
		float yaw   = std::atan2(2.0f * (w * z + x * y),
					1.0f - 2.0f * (y * y + z * z));

		return Eigen::Vector3f(roll, pitch, yaw);
	}

	/**
	* @brief 从四元数中提取偏航角（yaw），并以度为单位返回
	* 
	* @param q  输入四元数 (Eigen::Quaternionf)，假设已归一化或在调用前已 normalize
	* @return float  yaw 角（单位：度）
	*/
	inline float getYawDegrees(const Eigen::Quaternionf& q)
	{
		// 调用已有的 quaternionToEuler()，返回 {roll, pitch, yaw}（弧度）
		Eigen::Vector3f euler = quaternionToEuler(q);
		float yawRad = euler[2];
		// 转换为度
		return yawRad * RAD2DEG;
	}

	inline float getYawError(const Eigen::Quaternionf& q_curr, const Eigen::Quaternionf& q_target) {
		float yaw_curr = getYawDegrees(q_curr);
		float yaw_target = getYawDegrees(q_target);
	    
		float error = yaw_target - yaw_curr;
	    
		// 将误差限制在 [-π, π]
		while (error > 180.0f) error -= 360.0f;
		while (error < -180.0f) error += 360.0f;
	    
		return error;
	    }

	/**
	* @brief 计算两个三维点之间的欧氏距离
	*
	* @param current_pos  当前坐标 (Eigen::Vector3f)
	* @param target_pos   目标坐标 (Eigen::Vector3f)
	* @return float       两点之间的欧氏距离
	*/
	inline float euclideanDistance(const Eigen::Vector3f& current_pos,
				const Eigen::Vector3f& target_pos)
	{
		// 1. 先做差，得到一个 Vector3f
		Eigen::Vector3f delta = current_pos - target_pos;
		// 2. 直接调用 .norm()，返回 √(x² + y² + z²)
		return delta.norm();
	}

	inline Eigen::Vector3f transformWorldToBody(
		const Eigen::Vector3f& T_wb,               // 机器人位置
		const Eigen::Quaternionf& Q_wb,            // 机器人朝向（世界系下）
		const Eigen::Vector3f& P_w)                // 目标点在世界系下
	    {
		return Q_wb.inverse() * (P_w - T_wb);
	    }


};//namespace WHU_ROBOT