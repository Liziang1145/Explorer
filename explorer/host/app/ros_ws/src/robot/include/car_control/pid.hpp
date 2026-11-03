#ifndef PID_CONTROLLER_H
#define PID_CONTROLLER_H

#include <algorithm> // for std::clamp

/**
 * @brief PID 控制器类
 * 
 * 使用方式示例：
 *   PID pid(1.0, 0.1, 0.01, -10.0, 10.0, -5.0, 5.0);
 *   double dt = 0.01; // 10 ms 控制周期
 *   while ( ... ) {
 *       double setpoint = 100.0;       // 目标值
 *       double measurement = readSensor();
 *       double control = pid.update(setpoint, measurement, dt);
 *       applyControl(control);
 *   }
 */
class PID {
public:
    /**
     * @brief 构造函数
     * 
     * @param Kp_      比例增益
     * @param Ki_      积分增益
     * @param Kd_      微分增益
     * @param outMin_  输出最小值（用于限制控制量）
     * @param outMax_  输出最大值（用于限制控制量）
     * @param integMin_ 积分项最小值（用于积分限幅，防止积分饱和）
     * @param integMax_ 积分项最大值（用于积分限幅，防止积分饱和）
     */
    PID(double Kp_, double Ki_, double Kd_,
        double outMin_, double outMax_,
        double integMin_ = -1e6, double integMax_ = 1e6)
        : Kp(Kp_), Ki(Ki_), Kd(Kd_),
          outMin(outMin_), outMax(outMax_),
          integMin(integMin_), integMax(integMax_),
          integrator(0.0), prevError(0.0), firstUpdate(true)
    {
    }

    /**
     * @brief 更新 PID 控制器，计算控制量
     * 
     * @param setpoint     目标值
     * @param measurement  测量值
     * @param dt           当前周期时间（单位：秒，必须大于 0）
     * @return double      控制输出（已在 [outMin, outMax] 范围内限幅）
     */
    double update(double setpoint, double measurement, double dt) {
        if (dt <= 0.0) {
            // 如果 dt 非法，则直接返回 0
            return 0.0;
        }

        // 计算误差
        double error = setpoint - measurement;

        // 比例项
        double Pout = Kp * error;

        // 积分项累加并限幅
        integrator += error * dt;
        integrator = std::clamp(integrator, integMin, integMax);
        double Iout = Ki * integrator;

        // 微分项（基于误差变化率）
        double derivative = 0.0;
        if (firstUpdate) {
            // 第一次更新时无法计算微分，可设置为 0
            derivative = 0.0;
            firstUpdate = false;
        } else {
            derivative = (error - prevError) / dt;
        }
        double Dout = Kd * derivative;

        // 记录本次误差，供下次计算微分项使用
        prevError = error;

        // 合成三项，得到未经限幅的控制量
        double output = Pout + Iout + Dout;

        // 输出限幅
        output = std::clamp(output, outMin, outMax);

        return output;
    }

    double update(double error, double dt) {
        if (dt <= 0.0) {
            // 如果 dt 非法，则直接返回 0
            return 0.0;
        }

        // 比例项
        double Pout = Kp * error;

        // 积分项累加并限幅
        integrator += error * dt;
        integrator = std::clamp(integrator, integMin, integMax);
        double Iout = Ki * integrator;

        // 微分项（基于误差变化率）
        double derivative = 0.0;
        if (firstUpdate) {
            // 第一次更新时无法计算微分，可设置为 0
            derivative = 0.0;
            firstUpdate = false;
        } else {
            derivative = (error - prevError) / dt;
        }
        double Dout = Kd * derivative;

        // 记录本次误差，供下次计算微分项使用
        prevError = error;

        // 合成三项，得到未经限幅的控制量
        double output = Pout + Iout + Dout;

        // 输出限幅
        output = std::clamp(output, outMin, outMax);

        return output;
    }

    /**
     * @brief 重置 PID 状态（一般在启动或重新设定目标前调用）
     */
    void reset() {
        integrator = 0.0;
        prevError = 0.0;
        firstUpdate = true;
    }

    /**
     * @brief 设置新的 PID 参数（可以在运行时动态调整）
     */
    void setTunings(double Kp_, double Ki_, double Kd_) {
        Kp = Kp_;
        Ki = Ki_;
        Kd = Kd_;
    }

    /**
     * @brief 设置输出上下限
     */
    void setOutputLimits(double min_, double max_) {
        outMin = min_;
        outMax = max_;
    }

    /**
     * @brief 设置积分限幅范围
     */
    void setIntegratorLimits(double min_, double max_) {
        integMin = min_;
        integMax = max_;
    }

private:
    // 三个增益
    double Kp;
    double Ki;
    double Kd;

    // 输出限幅
    double outMin;
    double outMax;

    // 积分限幅（防止积分风up）
    double integMin;
    double integMax;

    // 内部状态
    double integrator;  // 积分项累加值
    double prevError;   // 上一次误差（用于微分项计算）
    bool firstUpdate;   // 标记是否第一次调用 update
};

#endif // PID_CONTROLLER_H
