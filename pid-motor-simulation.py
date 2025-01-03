import numpy as np
import matplotlib.pyplot as plt
from matplotlib.widgets import Slider

# Initialise random seed
rng = np.random.default_rng(seed=1)

# Motor parameters as constant global parameters
J = 0.005       # Moment of inertia [kgm^2]
K = 0.147       # Torque constant [Nm/A]/back EMF constant [V/rad/s]
B = 0.001       # Damping coefficient [Nms]
L = 0.083       # Armature inductance [H]
R = 1.03        # Armature resistance [Ohm]

def motor_model(y, z, t):
    """
    Calculates the first derivatives for the angular velocity
    and the armature current.
    These two differential equations describe the mechanical model
    and the electrical model of a DC motor respectively.

    The motor torque constant (Kt) describes the relation between 
    the armature current and the generated torque.
    The back EMF constant (Ke) relates the electromotive force 
    generated by the motor to its angular velocity. 
    These constants have the same numerical value in SI units.

    Args: 
    y (array): the output vector [w, I], angular velocity and armature current
    z (array): the input vector [V, TL], input voltage and load torque
    t (float): redundant, included for code reusability

    returns:
    array,  numerical values for the derivatives
    """
    w, I = y
    V, TL = z
    dwdt = (K*I-B*w-TL)/J
    dIdt = (V-K*w-R*I)/L
    return np.array([dwdt, dIdt])

def load_disturbance(magnitude, T):
    """
    Simulates disturbances in motor load using filtered Gaussian noise

    Args: 
    magnitude (float): magnitude of the disturbances
    T (array): simulation time vector

    returns:
    array,  load disturbance vector
    """
    # Create Gaussian noise and scale it
    disturbance = magnitude*rng.normal(0, 1, T.shape[0])
    
    # Pass through low-pass filter
    for i in range(T.shape[0]):
        disturbance[i] = low_pass_filter(disturbance[i], disturbance[i-1], 0.95)
    return disturbance

def rk4_step(f, y, z, t, h):
    """
    Calculates the function y one timestep forward using
    fourth order Runge-Kutta method. The global truncation error
    is in the order of h^4.

    Args: 
    f (function): derivative function for y
    y (array): functions to be solved
    z (array): additional parameters to f
    t (float): time
    h (float): step size

    returns:
    array,  y at next time step
    """
    k1 = h*f(y, z, t)
    k2 = h*f(y + k1/2, z, t + h/2)
    k3 = h*f(y + k2/2, z, t + h/2)
    k4 = h*f(y + k3, z, t + h)
    return y + (k1 + 2*k2 + 2*k3 + k4)/6

def euler_step(f, y, z, t, h):
    """
    Calculates the function y one timestep forward using
    the forward Euler method. The global truncation error
    is in the order of h.

    Args: 
    f (function): derivative function for y
    y (array): functions to be solved
    z (array): additional parameters to f
    t (float): time
    h (float): step size

    returns:
    array,  y at next time step
    """
    return y + h*f(y, z, t)
    
def PID_update(Kp, Ki, Kd, error_value, error_sum, error_rate):
    """
    Calculates the control signal using parallel PID control rule

    Args: 
    Kp (float): proportional gain
    Ki (float): integral gain
    Kd (float): derivative gain
    error_value (float): instantaneous error
    error_sum (float): cumulative sum of errors
    error_rate (float): rate of change of error

    returns:
    float,  control signal value
    """
    return Kp*error_value + Ki*error_sum + Kd*error_rate

def low_pass_filter(current_value, previous_value, lpf_weight = 0):
    """
    First order low-pass filter with adjusted weight. 
    Filters the given signal by taking a weighted sum.

    Args: 
    current_value (float): current value
    previous_value (float): previous value
    lpf_weight (float): weight for the lpf sum

    returns:
    float,  filtered signal value
    """
    # Adjusts the weight to make the smoothing non-linear
    lpf_weight = 1 - (1 - lpf_weight)**2
    # Returns the weighted sum
    return (1 - lpf_weight)*current_value + lpf_weight*previous_value

def run_simulation(Kp, Ki, Kd, lpf_weight, pnoise_level, mnoise_level, Ts, t_end, dt, w_ref=40, solver='rk4'):
    """
    Runs the simulation of a DC motor with PID velocity control.

    The simulation starts by setting up initial values and creating arrays to hold the results.
    Next, the noise models are created and an apparent sampling frequency f is calculated.

    After the initialisation, the main loop starts. At each simulation step, the DC motor
    equations are solved using either RK4 or forward Euler solver. At every f steps, the 
    error values are calculated and the control signal updated with PID control rule.

    Args: 
    Kp (float): proportional gain
    Ki (float): integral gain
    Kd (float): derivative gain
    lpf_weight (float): weight for the lpf sum
    pnoise_level (float): process noise level
    mnoise_level (float): measurement noise level
    Ts (float): control loop sample time
    t_end (float): simulation end time
    dt (float): simulation time step
    w_ref (float): reference angular velocity
    solver (string): solver to be used, 'rk4' or 'euler'

    returns:
    w (float): angular velocity of the motor vector
    w_measured (float): measured angular velocity vector
    I (array): armature current vector 
    u (array): control signal vector 
    error_value (array): instantaneous error vector
    error_sum (array): cumulative sum of errors vector
    error_rate (array): rate of change of error vector 
    T (array): simulation time vector
    """

    # Define time vector
    T = np.arange(0, t_end, dt)

    # Motor initial conditions
    w0 = 0.0
    I0 = 0.0
    y = np.array([w0, I0])
 
    # Initialise arrays to hold the results
    w = np.zeros(T.shape[0])
    w_measured = np.zeros(T.shape[0])
    I = np.zeros(T.shape[0])
    u = np.zeros(T.shape[0])

    # Initialise arrays to hold the error terms
    error_value = np.zeros(T.shape[0])
    error_sum = np.zeros(T.shape[0])
    error_rate = np.zeros(T.shape[0])

    # Calculate process noise
    # Applied as disturbances in the motor load
    # Modelled as low-pass filtered Gaussian noise
    process_noise = load_disturbance(pnoise_level, T)

    # Calculate measurement noise
    # Applied as sensor noise without bias
    # Modelled with zero mean Gaussian noise
    measurement_noise = mnoise_level*rng.normal(0, 1, T.shape[0])

    # Calculate the approximate sampling frequency of the control loop
    f = round(Ts/dt)

    for i in range(T.shape[0]):

        # Update the angular velocity and armature current values
        w[i] = y[0]
        I[i] = y[1]

        # Calculate the measured angular velocity
        w_measured[i] = w[i] + measurement_noise[i]

        # Runs the control loop and updates the input signal at predefined frequency
        if i%f == 0:

            # Calculates the error signal by taking the difference
            # between the reference value and the measured value
            error_value[i] = w_ref - w_measured[i]
            
            # Calculates the cumulative sum of errors
            error_sum[i] = error_sum[i-1] + error_value[i-1]*f*dt

            # Checks if derivative gain Kd is used
            if Kd > 0:

                # Calculates the rate of change of the error signal
                error_rate[i] = (error_value[i]-error_value[i-f])/(f*dt)

                # First order low-pass filter for the error rate of change
                error_rate[i] = low_pass_filter(error_rate[i], error_rate[i-1], lpf_weight)

            # Calculates the control signal using parallel PID controller
            u[i] = PID_update(Kp, Ki, Kd, error_value[i], error_sum[i], error_rate[i])

        # Zero-order hold intersample behaviour
        else:
            error_value[i] = error_value[i-1]
            error_sum[i] = error_sum[i-1]
            error_rate[i] = error_rate[i-1]

            u[i] = u[i-1]

        # Chooses which solver to use
        if solver == 'euler':
            # The next values for output are calculated and process noise is added
            y = euler_step(motor_model, y, [u[i], process_noise[i]], T[i], dt)
        else:
            y = rk4_step(motor_model, y, [u[i], process_noise[i]], T[i], dt)

    return w, w_measured, I, u, error_value, error_sum, error_rate, T

def interactive_plot(t_end=2, dt=0.001, w_ref = 40):
    """
    Opens an interactive plot with for analysis of the simulation.
    The figure contains 4 subplots in a 2x2 grid:

        1: angular velocity of the motor
        2: P, I and D components of the control signal
        3: angular velocity, armature current and input voltage/control signal
        4: angular velocity and the measured angular velocity

    The parameters of the simulation can be adjusted with the following sliders:

        solver: changes solver between RK4 and Euler. Latter might be better for slower systems.
        process noise: injects filtered Gaussian noise to the load torque.
                        At maximum value switches to step disturbance.
        measurement noise: adds Gaussian noise to the angular velocity measurements.
        Kp: adjusts the proportional gain
        Ki: adjusts the integral gain
        Kd: adjusts the derivative gain
        lpf: adjusts the low-pass filter weight
        Ts: adjusts the control loop sample time

    Args: 
    t_end (float): simulation end time
    dt (float): simulation time step, increase for faster performance
    w_ref (float): reference angular velocity

    returns:
    a nice plot
    """

    # Creates a figure with 1.5 times the default size
    fig = plt.figure(figsize=[9.6, 7.2])

    # Creates a 2x2 grid of plots
    ax_up_left = fig.add_subplot(221)
    ax_up_right = fig.add_subplot(222)
    ax_down_left = fig.add_subplot(223)
    ax_down_right = fig.add_subplot(224)

    # Adjusts the position of the grid
    fig.subplots_adjust(top=0.95, bottom=0.4)

    # Parameters for the initial simulation
    Kp = 0.2
    Ki = 1.15
    Kd = 0.0
    Ts = dt
    solver = 0
    lpf_weight = 0
    mnoise_level = 0
    pnoise_level = 0

    # Used to assign 0: rk4, 1: euler
    solver_dict = ['rk4', 'euler']

    # Calculates the values for the initial plots
    w, w_measured, I, u, error_value, error_sum, error_rate, T = run_simulation(Kp, Ki, Kd, lpf_weight, pnoise_level, mnoise_level, Ts, t_end, dt, w_ref, solver_dict[solver])

    # Plots a horizontal line at the 15 % overshoot limit
    ax_up_left.hlines(1.15*w_ref, 0, t_end, colors='red', linestyles='dashed', linewidth=1)
    # Plots a vertical line at the 0.3 s settling time limit
    ax_up_left.vlines(0.3, 0, 1.05*w_ref, colors='gray', linestyles='dashed', linewidth=1)
    # Fills up the space between +-5 % settling limits
    ax_up_left.fill_between([0.3, t_end], 1.05*w_ref, 0.95*w_ref, color='lightgray')
    # Creates a 2D line object and plots the initial simulation results
    # Objects are named after their location in the grid
    # Ul = upper row, left columns
    [line_ul_1] = ax_up_left.plot(T, w, linewidth=2, color='blue', label='w')
    # Prints the legend and sets the location to upper right corner
    ax_up_left.legend(loc=1)
    # Sets the axis limits
    ax_up_left.set_xlim([-0.1, t_end+0.1])
    ax_up_left.set_ylim([0, 2*w_ref])

    # Repeats the process for the other subplots
    [line_ur_1] = ax_up_right.plot(T, Kp*error_value, linewidth=2, color='green', label='P')
    [line_ur_2] = ax_up_right.plot(T, Ki*error_sum, linewidth=2, color='red', label='I')
    [line_ur_3] = ax_up_right.plot(T, Kd*error_rate, linewidth=2, color='purple', label='D')
    ax_up_right.legend(loc=1)
    ax_up_right.set_xlim([-0.1, t_end+0.1])
    ax_up_right.set_ylim([-w_ref/2, 2*w_ref])

    [line_dl_1] = ax_down_left.plot(T, w, linewidth=2, color='blue')
    [line_dl_2] = ax_down_left.plot(T, u, linewidth=2, color='pink', label='u')
    [line_dl_3] = ax_down_left.plot(T, I, linewidth=2, color='orange', label='I')
    ax_down_left.legend(loc=1)
    ax_down_left.set_xlim([-0.1, t_end+0.1])
    ax_down_left.set_ylim([-w_ref/2, 2*w_ref])

    [line_dr_1] = ax_down_right.plot(T, w_measured, linewidth=2, color='lightblue', label='w measured')
    [line_dr_2] = ax_down_right.plot(T, w, linewidth=2, color='blue')
    ax_down_right.legend(loc=1)
    ax_down_right.set_xlim([-0.1, t_end+0.1])
    ax_down_right.set_ylim([0, 2*w_ref])

    # Slider that controls the solver variable

    solver_slider_ax = fig.add_axes([0.2, 0.25, 0.03, 0.03])
    solver_slider = Slider(solver_slider_ax, 'solver', 0, 1, valinit=0, valstep=[0, 1])
    solver_slider.valtext.set_text('RK4')
    solver_slider.label.set_x(1.5)
    solver_slider.label.set_y(1.5)
    solver_slider.valtext.set_x(1.5)

    # Slider that controls the measurement noise level variable
    mnoise_slider_ax = fig.add_axes([0.55, 0.25, 0.3, 0.03])
    mnoise_slider = Slider(mnoise_slider_ax, 'measurement noise', 0, 10, valinit=mnoise_level, valfmt='%.2f')
    mnoise_slider.label.set_x(0.5)
    mnoise_slider.label.set_y(1.5)

    # Slider that controls the process noise level variable
    pnoise_slider_ax = fig.add_axes([0.3, 0.25, 0.2, 0.03])
    pnoise_slider = Slider(pnoise_slider_ax, 'process noise', 0, 5, valinit=pnoise_level, valfmt='%.2f')
    pnoise_slider.label.set_x(0.5)
    pnoise_slider.label.set_y(1.5)

    # Slider that controls the proportional gain variable
    Kp_slider_ax  = fig.add_axes([0.2, 0.2, 0.65, 0.03])
    Kp_slider = Slider(Kp_slider_ax, 'Kp', 0.0, 3, valinit=Kp, valfmt='%.2f')

    # Slider that controls the integral gain variable
    Ki_slider_ax = fig.add_axes([0.2, 0.15, 0.65, 0.03])
    Ki_slider = Slider(Ki_slider_ax, 'Ki', 0.0, 5, valinit=Ki, valfmt='%.2f')

    # Slider that controls the derivative gain variable
    Kd_slider_ax = fig.add_axes([0.2, 0.1, 0.3, 0.03])
    Kd_slider = Slider(Kd_slider_ax, 'Kd', 0.0, 0.5, valinit=Kd, valfmt='%.2f')

    # Slider that controls the low-pass filter variable
    lpf_slider_ax = fig.add_axes([0.6, 0.1, 0.25, 0.03])
    lpf_slider = Slider(lpf_slider_ax, 'lpf', 0, 1, valinit=lpf_weight, valfmt='%.2f')
    lpf_slider.label.set_x(-0.07)

    # Slider that controls the control loop sample time variable
    Ts_slider_ax = fig.add_axes([0.2, 0.05, 0.65, 0.03])
    Ts_slider = Slider(Ts_slider_ax, 'Ts', Ts, 0.3, valinit=Ts, valfmt='%.2f')

    # Function that is called every time a slider moves
    # Updates the y data of the plots
    def update_plots(val):
        
        # Updates the solver label
        if solver_slider.val:
            solver_slider.valtext.set_text('Euler')
        else:
            solver_slider.valtext.set_text('RK4')

        # Runs the simulation and updates the values
        w, w_measured, I, u, error_value, error_sum, error_rate = run_simulation(Kp_slider.val, Ki_slider.val, Kd_slider.val, lpf_slider.val, pnoise_slider.val, mnoise_slider.val, Ts_slider.val, t_end, dt, w_ref, solver_dict[solver_slider.val])[0:7]

        #Updates the 2D lines in each plot
        line_ul_1.set_ydata(w)
        line_ur_1.set_ydata(Kp_slider.val*error_value)
        line_ur_2.set_ydata(Ki_slider.val*error_sum)
        line_ur_3.set_ydata(Kd_slider.val*error_rate)
        line_dl_1.set_ydata(w)
        line_dl_2.set_ydata(u)
        line_dl_3.set_ydata(I)
        line_dr_1.set_ydata(w_measured)
        line_dr_2.set_ydata(w)

        # Draws the new lines and flushes any events
        fig.canvas.draw_idle()
        fig.canvas.flush_events()

    # Updates the plots when sliders are moved
    Kp_slider.on_changed(update_plots)
    Ki_slider.on_changed(update_plots)
    Kd_slider.on_changed(update_plots)
    lpf_slider.on_changed(update_plots)
    Ts_slider.on_changed(update_plots)
    solver_slider.on_changed(update_plots)
    mnoise_slider.on_changed(update_plots)
    pnoise_slider.on_changed(update_plots)

    plt.show()

def main():
    interactive_plot()
    
# Execute main() if the program is launched as a script, 
# but not if it is imported as a module
if __name__ == "__main__":
    main()