% 示例数据（假设时间范围为 0~10s，采样点数 100）
t = 0:0.1:10; % 时间向量

% 笛卡尔坐标误差（单位：mm）
x_error = 0.5*sin(t/2) + 0.1*randn(size(t)); % X轴误差
y_error = 0.3*cos(t) + 0.1*randn(size(t));    % Y轴误差
z_error = 0.4*sin(t) + 0.1*randn(size(t));     % Z轴误差

% 欧拉角误差（单位：rad）
roll_error = 0.02*sin(t) + 0.005*randn(size(t)); % 滚转角误差
pitch_error = 0.015*cos(2*t) + 0.005*randn(size(t)); % 俯仰角误差
yaw_error = 0.01*sin(t/1.5) + 0.005*randn(size(t));  % 偏航角误差

% 创建2行3列子图
figure('Units','normalized','Position',[0.1 0.1 0.8 0.8]);
set(gcf,'Color','w'); % 白色背景

% 第一行：笛卡尔坐标误差
subplot(2,3,1);
plot(t, x_error, 'b', 'LineWidth',1.2);
title('X轴位置误差');
xlabel('时间 (s)');
ylabel('误差 (mm)');
grid on;
legend('X轴误差');

subplot(2,3,2);
plot(t, y_error, 'g', 'LineWidth',1.2);
title('Y轴位置误差');
xlabel('时间 (s)');
ylabel('误差 (mm)');
grid on;
legend('Y轴误差');

subplot(2,3,3);
plot(t, z_error, 'r', 'LineWidth',1.2);
title('Z轴位置误差');
xlabel('时间 (s)');
ylabel('误差 (mm)');
grid on;
legend('Z轴误差');

% 第二行：欧拉角误差
subplot(2,3,4);
plot(t, roll_error*rad2deg(1), 'b', 'LineWidth',1.2); % 转换为角度显示
title('滚转角误差');
xlabel('时间 (s)');
ylabel('误差 (°)');
grid on;
legend('滚转角误差');

subplot(2,3,5);
plot(t, pitch_error*rad2deg(1), 'g', 'LineWidth',1.2);
title('俯仰角误差');
xlabel('时间 (s)');
ylabel('误差 (°)');
grid on;
legend('俯仰角误差');

subplot(2,3,6);
plot(t, yaw_error*rad2deg(1), 'r', 'LineWidth',1.2);
title('偏航角误差');
xlabel('时间 (s)');
ylabel('误差 (°)');
grid on;
legend('偏航角误差');

% 调整子图间距
sgtitle('末端轨迹误差分析', 'FontSize',14);