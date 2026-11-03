#pragma once

#include "CarControlBase.hpp"
#include "configParser.hpp"
#include <iostream>
#include "pid.hpp"
#include <cmath>
#include <chrono>
#include "boost/sml.hpp"
#include <cstdio>

namespace WHU_ROBOT{

	namespace sml = boost::sml;

	struct ControlInterface {
	
		ControlInterface(const ctl_param_t& _param):
			param{_param},
			pid_vx{param.p_vx, 0, param.d_vx, -param.max_v, param.max_v},
			pid_vy{param.p_vy, 0, param.d_vy, -param.max_v, param.max_v},
			pid_wz{param.p_wz, 0, param.d_wz, -param.max_w, param.max_w}
		{

		}

		//------------------------const-----------
		static constexpr float __vx_when_spin = 0.0;
		//-----------------------obj-------------
		ctl_param_t param;
		PID pid_vx;
		PID pid_vy;
		PID pid_wz;

		//-----------------------state-------------
		Eigen::Vector3f current_pos;//in Body, always (0,0,0)
		// float current_yaw;
		CarState current_state;
		Eigen::Vector3f target_pos;//in Body
		// float target_yaw;
		CarState target_state;

		CarState compute_result;

		//----------------------utils--------------
		bool __flag_get_target = 0;
		bool __flag_get_current = 0;

		bool enable_control = 0;

		double last_dt = 0.0;

		void generate_cmd(uint8_t mode, float vx, float vy, float wz){
			static uint32_t __cnt = 0;
			CarState rtn{};
			if(mode == 6){//4T4D
				rtn.mode = 6;
				
				rtn.base_lin_vel.setZero();
				rtn.base_lin_vel.x() = __vx_when_spin;

				rtn.base_ang_vel.setZero();
				rtn.base_ang_vel.z() = wz;
			} else if(mode == 8){//parallel
				rtn.mode = 8;
				
				rtn.base_lin_vel.setZero();
				rtn.base_lin_vel.x() = vx;
				rtn.base_lin_vel.y() = vy;

				rtn.base_ang_vel.setZero();
			} else if (mode == 2){//free
				rtn.mode = 2;
				rtn.base_lin_vel.setZero();
				rtn.base_ang_vel.setZero();
			} else {//stop
				rtn.mode = 1;
				rtn.base_lin_vel.setZero();
				rtn.base_ang_vel.setZero();
			}
			
			compute_result = rtn;
		}

	};

	namespace HSM{
		//event
		struct timetick {
			double dt;
		};

		struct terminate {};

		//guard
		struct IfGetCurrentGuard {
			bool operator()(WHU_ROBOT::ControlInterface& interface) const noexcept {
				return interface.__flag_get_current;
			}
		};
		auto if_get_current = IfGetCurrentGuard{};

		struct IfGetTargetGuard {
			bool operator()(WHU_ROBOT::ControlInterface& interface) const noexcept {
				return interface.__flag_get_target;
			}
		};
		auto if_get_target = IfGetTargetGuard{};

		struct IfStopFlagGuard {
			bool operator()(WHU_ROBOT::ControlInterface& interface) const noexcept {
				return !interface.enable_control;
			}
		};
		auto if_stop_flag = IfStopFlagGuard{};

		struct IfErrYawGuard {
			bool operator()(WHU_ROBOT::ControlInterface& interface) const noexcept {
				return std::abs(
					getYawError(interface.current_state.base_quat, interface.target_state.base_quat)) 
						>= interface.param.delta_yaw;
			}
		};
		auto if_err_yaw = IfErrYawGuard{};

		struct IfErrXYGuard {
			bool operator()(WHU_ROBOT::ControlInterface& interface) const noexcept {
				return euclideanDistance(interface.current_pos, interface.target_pos) 
					>= interface.param.delta_distance;
			}
		};
		auto if_err_xy = IfErrXYGuard{};

		struct IfUnhealthyGuard {
			bool operator()(WHU_ROBOT::ControlInterface& interface) const noexcept {
				return euclideanDistance(interface.current_pos, interface.target_pos) 
					>= interface.param.brake_distance;
			}
		};
		auto if_unhealthy = IfUnhealthyGuard{};


		//action
		struct ActionStop {
			void operator()(WHU_ROBOT::ControlInterface& interface) noexcept {
				interface.generate_cmd(1, 0,0,0);
			}
		};
		auto action_stop = ActionStop{};

		struct ActionFree {
			void operator()(WHU_ROBOT::ControlInterface& interface) noexcept {
				interface.generate_cmd(2, 0,0,0);
			}
		};
		auto action_free = ActionFree{};

		struct ActionYaw {
			void operator()(const auto& event, WHU_ROBOT::ControlInterface& interface) noexcept {
				const auto& e = static_cast<const timetick&>(event);
				float wz = interface.pid_wz.update(
					getYawError(interface.current_state.base_quat, interface.target_state.base_quat),
					e.dt);
				interface.generate_cmd(6, 0,0,wz);
			}
		};
		auto action_yaw = ActionYaw{};

		struct ActionXY {
			void operator()(const auto& event, WHU_ROBOT::ControlInterface& interface) noexcept {
				const auto& e = static_cast<const timetick&>(event);
				float vx = interface.pid_vx.update(
					interface.target_pos.x(), 
					interface.current_pos.x(), 
					e.dt);
				float vy = interface.pid_vy.update(
					interface.target_pos.y(), 
					interface.current_pos.y(), 
					e.dt);

				interface.generate_cmd(8, vx,vy,0);
			}
		};
		auto action_xy = ActionXY{};

		struct ActionLog {
			void operator()(WHU_ROBOT::ControlInterface& interface) noexcept {
				std::cout<<"\033[31m" << "action_log:" << "\033[0m" << std::endl;
				std::cout<<"current position: "<< interface.current_pos.transpose() <<std::endl;
				std::cout<<"target position: "<< interface.target_pos.transpose() <<std::endl;
			}
		};
		auto action_log = ActionLog{};

		//HSM
		//sub sm
		struct moving {
			auto operator()() {
				using namespace sml;
				return make_transition_table(
					"xy_control"_s + on_entry<_> / [](ControlInterface& interface)
					{
						interface.pid_vx.reset();
						interface.pid_vy.reset();
					},
					"xy_control"_s + event<timetick> [(! if_err_xy) && if_err_yaw] 
						= "yaw_control"_s,
					"xy_control"_s(H) + event<timetick> [if_err_xy] / action_xy ,

					"yaw_control"_s + on_entry<_> / [](ControlInterface& interface)
					{
						interface.pid_wz.reset();
					},
					"yaw_control"_s + event<timetick> [if_err_xy] = "xy_control"_s,
					"yaw_control"_s + event<timetick> [if_err_yaw] / action_yaw
				);
			}
		};

		//main sm
		struct car_sm {
			auto operator()() {
				using namespace sml;
				return make_transition_table(
					*"terminate_handle"_s + event<timetick> [if_unhealthy] 
						/ (action_log,action_stop) = X,
					"terminate_handle"_s + event<terminate> / action_stop = X,
					"terminate_handle"_s + unexpected_event<_> / action_stop = X,

					
					*"unready"_s + event<timetick> [if_get_current && if_get_target] = "stop"_s,
					"unready"_s + event<timetick> [(! if_get_current) || (! if_get_target)] 
						/ action_stop ,

					"stop"_s + event<timetick> [
							(! if_stop_flag) 
							&& (! if_err_yaw)
							&& (! if_err_xy)
						] = "free"_s,
					"stop"_s + event<timetick> [
							(! if_stop_flag) 
							&& (if_err_yaw || if_err_xy)
						] = state<moving>,
					"stop"_s + event<timetick> [if_stop_flag] / action_stop ,


					state<moving> +  event<timetick> [if_stop_flag] = "stop"_s,
					state<moving> +  event<timetick> [(!if_stop_flag)&&(!if_err_xy)&&(!if_err_yaw)] = "free"_s,

					"free"_s + event<timetick> [(!if_stop_flag)&&(if_err_xy || if_err_yaw)] = state<moving>,
					"free"_s + event<timetick> [if_stop_flag] = "stop"_s,
					"free"_s + event<timetick> / action_free 
				);
			}
		};

		//logger
		struct my_logger {
			private:
				std::string last_process_event;
				std::string last_guard;
				std::string last_action;
				std::string last_transition;
			
			public:
				template <class SM, class TEvent>
				void log_process_event(const TEvent&) {
					std::string msg = "[" + std::string(sml::aux::get_type_name<SM>()) + "][process_event] " + sml::aux::get_type_name<TEvent>();
					if (msg != last_process_event) {
						std::cout << msg << std::endl;
						last_process_event = msg;
					}
				}
			
				template <class SM, class TGuard, class TEvent>
				void log_guard(const TGuard&, const TEvent&, bool result) {
					std::string msg = "[" + std::string(sml::aux::get_type_name<SM>()) + "][guard] " +
									  sml::aux::get_type_name<TGuard>() + " " +
									  sml::aux::get_type_name<TEvent>() + " " + (result ? "[OK]" : "[Reject]");
					if (msg != last_guard) {
						std::cout << msg << std::endl;
						last_guard = msg;
					}
				}
			
				template <class SM, class TAction, class TEvent>
				void log_action(const TAction&, const TEvent&) {
					std::string msg = "[" + std::string(sml::aux::get_type_name<SM>()) + "][action] " +
									  sml::aux::get_type_name<TAction>() + " " + sml::aux::get_type_name<TEvent>();
					if (msg != last_action) {
						std::cout << msg << std::endl;
						last_action = msg;
					}
				}
			
				template <class SM, class TSrcState, class TDstState>
				void log_state_change(const TSrcState& src, const TDstState& dst) {
					std::string msg = "[" + std::string(sml::aux::get_type_name<SM>()) + "][transition] " +
									  src.c_str() + " -> " + dst.c_str();
					if (msg != last_transition) {
						std::cout << msg << std::endl;
						last_transition = msg;
					}
				}
		};
			
	}


	class SimpleCtrl final : public CarControllerBase{
	public:
		SimpleCtrl(const ctl_param_t& _param):
			param{_param},
			interface{param}
		{
			lastTime_ = Clock::now();

		}

		~SimpleCtrl() {
			sm.process_event(HSM::terminate{});
		};

		void feedTarget(const CarState& targetState) override {
			static constexpr uint8_t MASK_ENABLE_CONTROL = 0b1000'0000;

			interface.target_state = targetState;

			if(targetState.mode & MASK_ENABLE_CONTROL){
				interface.enable_control = 1;
			} else {
				interface.enable_control = 0;
			}

			if(!interface.__flag_get_current){
				return;
			}else {
				interface.__flag_get_target = 1;
				interface.target_pos = transformWorldToBody(interface.current_state.base_pos, 
							interface.current_state.base_quat, targetState.base_pos);
				targetState.base_pos;
				interface.target_pos.z() = 0.0;
				// interface.target_yaw = getYawDegrees(targetState.base_quat);
			}
		}

		void feedCurrent(const CarState& currentState) override {
			interface.__flag_get_current = 1;
			interface.current_state = currentState;
			// interface.current_pos = currentState.base_pos;
			interface.current_pos = Eigen::Vector3f(0,0,0);
			// interface.current_pos.z() = 0.0;
			// interface.current_yaw = getYawDegrees(currentState.base_quat);
		}

		CarState computeControlOnce(void) override {
			Clock::time_point now = Clock::now();
			std::chrono::duration<double> delta = now - lastTime_;
			double dt = delta.count();
			lastTime_ = now;

			interface.last_dt = dt;
			sm.process_event(HSM::timetick{dt});

			return interface.compute_result;
		};
	private:
		ctl_param_t param;
		using Clock = std::chrono::steady_clock;
		Clock::time_point lastTime_;
		ControlInterface interface;
		HSM::my_logger logger{};
		sml::sm<HSM::car_sm, sml::logger<HSM::my_logger>> sm{logger, interface};
		// sml::sm<HSM::car_sm> sm{interface};
		
	};

};//namespace WHU_ROBOT

