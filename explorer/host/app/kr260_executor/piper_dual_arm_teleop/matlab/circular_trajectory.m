% Test script for getCircularTranjectory.m
clear; clc; close all;

% Parameters
origin = [0.45; 0; 0.5];            % Center of the circle
radius = 0.3;                       % Circle radius
period = 5.0;                       % Time for one full revolution (seconds)
duration = 10.0;                    % Total time to simulate
dt = 0.01;                          % Time step
times = 0:dt:duration;

% Orientation of the circular plane (45° rotation around x-axis)
angle_deg = 45;
axis = [0, 1, 0];
angle_rad = deg2rad(angle_deg);
axis = axis / norm(axis);
qw = cos(angle_rad / 2);
qx = axis(1) * sin(angle_rad / 2);
qy = axis(2) * sin(angle_rad / 2);
qz = axis(3) * sin(angle_rad / 2);
circle_orientation = [qw; qx; qy; qz]; % [w; x; y; z]

% Generate trajectory
trajectory = zeros(3, numel(times));
for i = 1:numel(times)
    trajectory(:, i) = getCircularTrajectory(circle_orientation, origin, radius, times(i), period);
end

% Plotting
figure;
plot3(trajectory(1, :), trajectory(2, :), trajectory(3, :), 'b', 'LineWidth', 2);
hold on;
plot3(origin(1), origin(2), origin(3), 'ro', 'MarkerSize', 10, 'MarkerFaceColor', 'r');
xlabel('X'); ylabel('Y'); zlabel('Z');
grid on; axis equal;
title('3D Circular Trajectory in Space');
view(3);

function pos = getCircularTrajectory(circle_orientation, origin, radius, time, period)
    % getCircularTranjectory generates a 3D point on a rotated circular trajectory
    % 
    % Inputs:
    %   circle_orientation - 4x1 quaternion vector [w, x, y, z]
    %   origin - 3x1 vector [x; y; z]
    %   radius - scalar, radius of circle
    %   time - current time
    %   period - period of one full revolution
    %
    % Output:
    %   pos - 3x1 position vector at the given time

    % Angular frequency
    omega = 2 * pi / period;

    % Angle
    angle = omega * time;

    % Local circle point (in XY plane)
    point_local = [radius * cos(angle);
                   radius * sin(angle);
                   0];

    % Convert quaternion to rotation matrix
    q = circle_orientation(:); % ensure column
    R = quat2rotm([q(1) q(2) q(3) q(4)]);  % MATLAB uses [w x y z]

    % Rotate to global space and translate
    pos = origin + R * point_local;
end
