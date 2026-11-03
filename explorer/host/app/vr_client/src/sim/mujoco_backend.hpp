/**
 * @file mujoco_backend.hpp
 * @author pansamic (pansamic@foxmail.com)
 * @brief MuJoCo physics engine backend.
 * @version 0.1
 * @date 2025-08-09
 * 
 * @copyright Copyright (c) 2025
 * 
 */
#pragma once

#include <mutex>
#include <array>
#include <vector>
#include <thread>
#include <Eigen/Core>
#include <mujoco/mujoco.h>
#include "modelxml.h"

template<typename T, std::size_t NumDof>
class MujocoBackend
{
public:
    explicit MujocoBackend()
    {
        mjSpec* s = mj_parseXMLString(piper_dual_arm_position_full_xml, nullptr, nullptr, 0);
        // mjSpec* s = mj_parseXML(PROJECT_PATH"/assets/mujoco_model/piper_dual_arm_torque_full.xml", nullptr, nullptr, 0);
        if ( s == nullptr )
        {
            throw std::runtime_error("MuJoCo failed to parse XML");
        }
        this->mujoco_model_ = mj_compile(s, nullptr);
        if ( this->mujoco_model_ == nullptr )
        {
            throw std::runtime_error("MuJoCo failed to compile model from spec");
        }
        this->mujoco_data_ = mj_makeData(this->mujoco_model_);
        if ( this->mujoco_data_ == nullptr )
        {
            throw std::runtime_error("MuJoCo failed to make data");
        }
    }
    ~MujocoBackend()
    {
        if ( this->mujoco_data_ != nullptr )
            mj_deleteData(this->mujoco_data_);
        if ( this->mujoco_model_ != nullptr )
            mj_deleteModel(this->mujoco_model_);
    }
    void update()
    {
        std::lock_guard<std::mutex>(this->mutex_);
        mj_step(this->mujoco_model_, this->mujoco_data_);
    }
    mjModel* getMujocoModel()
    {
        return this->mujoco_model_;
    }
    mjData* getMujocoData()
    {
        return this->mujoco_data_;
    }
    
    void setLeftArmJointControl(Eigen::Vector<T, NumDof> q)
    {
        std::lock_guard<std::mutex>(this->mutex_);
        for ( int i=0 ; i<NumDof ; ++i )
        {
            this->mujoco_data_->ctrl[i] = q(i);
        }
    }

    void setLeftArmJointControl(std::array<T, NumDof> q)
    {
        std::lock_guard<std::mutex>(this->mutex_);
        for ( int i=0 ; i<NumDof ; ++i )
        {
            this->mujoco_data_->ctrl[i] = q[i];
        }
    }

    void setLeftArmJointControl(std::vector<T> q)
    {
        if ( q.size() != NumDof )
        {
            return ;
        }
        std::lock_guard<std::mutex>(this->mutex_);
        for ( int i=0 ; i<NumDof ; ++i )
        {
            this->mujoco_data_->ctrl[i] = q[i];
        }
    }

    void setRightArmJointControl(Eigen::Vector<T, NumDof> q)
    {
        std::lock_guard<std::mutex>(this->mutex_);
        for ( int i=0 ; i<NumDof ; ++i )
        {
            this->mujoco_data_->ctrl[NumDof + 2 + i] = q(i); // 2 for two finger joints.
        }
    }

    void setRightArmJointControl(std::array<T, NumDof> q)
    {
        std::lock_guard<std::mutex>(this->mutex_);
        for ( int i=0 ; i<NumDof ; ++i )
        {
            this->mujoco_data_->ctrl[NumDof + 2 + i] = q[i]; // 2 for two finger joints.
        }
    }

    void setRightArmJointControl(std::vector<T> q)
    {
        if ( q.size() != NumDof )
        {
            return ;
        }
        std::lock_guard<std::mutex>(this->mutex_);
        for ( int i=0 ; i<NumDof ; ++i )
        {
            this->mujoco_data_->ctrl[NumDof + 2 + i] = q[i]; // 2 for two finger joints.
        }
    }

    Eigen::Vector<T, NumDof> getLeftArmJointPosition() const
    {
        std::lock_guard<std::mutex>(this->mutex_);
        Eigen::Vector<T, NumDof> joint_pos;
        for ( std::size_t i=0 ; i<NumDof ; ++i )
        {
            joint_pos(i) = this->mujoco_data_->qpos[i];
        }
        return joint_pos;
    }

    Eigen::Vector<T, NumDof> getLeftArmJointVelocity() const
    {
        std::lock_guard<std::mutex>(this->mutex_);
        Eigen::Vector<T, NumDof> joint_vel;
        for ( std::size_t i=0 ; i<NumDof ; ++i )
        {
            joint_vel(i) = this->mujoco_data_->qvel[i];
        }
        return joint_vel;
    }

    Eigen::Vector<T, NumDof> getLeftArmJointAcceleration() const
    {
        std::lock_guard<std::mutex>(this->mutex_);
        Eigen::Vector<T, NumDof> joint_acc;
        for ( std::size_t i=0 ; i<NumDof ; ++i )
        {
            joint_acc(i) = this->mujoco_data_->qacc[i];
        }
        return joint_acc;
    }

    Eigen::Vector<T, NumDof> getRightArmJointPosition() const
    {
        std::lock_guard<std::mutex>(this->mutex_);
        Eigen::Vector<T, NumDof> joint_pos;
        for ( std::size_t i=0 ; i<NumDof ; ++i )
        {
            joint_pos(i) = this->mujoco_data_->qpos[NumDof + 2 + i];
        }
        return joint_pos;
    }

    Eigen::Vector<T, NumDof> getRightArmJointVelocity() const
    {
        std::lock_guard<std::mutex>(this->mutex_);
        Eigen::Vector<T, NumDof> joint_vel;
        for ( std::size_t i=0 ; i<NumDof ; ++i )
        {
            joint_vel(i) = this->mujoco_data_->qvel[NumDof + 2 + i];
        }
        return joint_vel;
    }

    Eigen::Vector<T, NumDof> getRightArmJointAcceleration() const
    {
        std::lock_guard<std::mutex>(this->mutex_);
        Eigen::Vector<T, NumDof> joint_acc;
        for ( std::size_t i=0 ; i<NumDof ; ++i )
        {
            joint_acc(i) = this->mujoco_data_->qacc[NumDof + 2 + i];
        }
        return joint_acc;
    }

    Eigen::Vector<T, 3> getLeftHandSitePosition() const
    {
        std::lock_guard<std::mutex>(this->mutex_);
        Eigen::Vector<T, 3> pos;
        pos(0) = this->mujoco_data_->site_xpos[0];
        pos(1) = this->mujoco_data_->site_xpos[1];
        pos(2) = this->mujoco_data_->site_xpos[2];
        return pos;
    }
    Eigen::Vector<T, 3> getRightHandSitePosition() const
    {
        std::lock_guard<std::mutex>(this->mutex_);
        Eigen::Vector<T, 3> pos;
        pos(0) = this->mujoco_data_->site_xpos[3];
        pos(1) = this->mujoco_data_->site_xpos[4];
        pos(2) = this->mujoco_data_->site_xpos[5];
        return pos;
    }
    Eigen::Matrix<T, 3, 3> getLeftHandSiteOrientation() const
    {
        std::lock_guard<std::mutex>(this->mutex_);
        Eigen::Matrix<T, 3, 3> R;
        R(0, 0) = this->mujoco_data_->site_xmat[0];
        R(0, 1) = this->mujoco_data_->site_xmat[1];
        R(0, 2) = this->mujoco_data_->site_xmat[2];
        R(1, 0) = this->mujoco_data_->site_xmat[3];
        R(1, 1) = this->mujoco_data_->site_xmat[4];
        R(1, 2) = this->mujoco_data_->site_xmat[5];
        R(2, 0) = this->mujoco_data_->site_xmat[6];
        R(2, 1) = this->mujoco_data_->site_xmat[7];
        R(2, 2) = this->mujoco_data_->site_xmat[8];
        return R;
    }
    Eigen::Matrix<T, 3, 3> getRightHandSiteOrientation() const
    {
        std::lock_guard<std::mutex>(this->mutex_);
        Eigen::Matrix<T, 3, 3> R;
        R(0, 0) = this->mujoco_data_->site_xmat[9];
        R(0, 1) = this->mujoco_data_->site_xmat[10];
        R(0, 2) = this->mujoco_data_->site_xmat[11];
        R(1, 0) = this->mujoco_data_->site_xmat[12];
        R(1, 1) = this->mujoco_data_->site_xmat[13];
        R(1, 2) = this->mujoco_data_->site_xmat[14];
        R(2, 0) = this->mujoco_data_->site_xmat[15];
        R(2, 1) = this->mujoco_data_->site_xmat[16];
        R(2, 2) = this->mujoco_data_->site_xmat[17];
        return R;
    }
private:
    mutable std::mutex mutex_;
    mjModel* mujoco_model_;
    mjData* mujoco_data_;
};