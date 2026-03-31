#! /bin/bash

#########################################################################################################################
#########################################################################################################################
###################	                                                                                  ###################
###################	title:	            	  CPU library                                             ###################
###################                                                                                   ###################
###################	description:	Library of functions for multi-process management                 ###################
###################                                                                                   ###################
###################	version:	0.2.2.0                                                               ###################
###################	notes:	        .                                                                 ###################
###################	bash version:   tested on GNU bash, version 4.2.53                                ###################
###################                                                                                   ###################
###################	autor: gamorosino                                                                 ###################
################### email: g.amorosino@gmail.com                                                      ###################
###################	                                                                                  ###################
#########################################################################################################################
#########################################################################################################################
###################                                                                                   ###################
###################	update: added function waiting4func                                               ###################
###################	                                                                                  ###################
#########################################################################################################################
#########################################################################################################################


CPUs_available () {
                        ############# ############# ############# ############# ############# ############# #############
                        #############  Stima il numero di processori liberi a partire dal carico della CPU  ############# 
                        ############# ############# ############# ############# ############# ############# #############                  
                        
			local cpu_load=$( echo $( top -b -n2 | grep "Cpu(s)" | awk '{print $2+$4}' | tail -n1 ))		# calcolo del carico della cpu%
			local cpu_load_f=$(echo "scale=5; ${cpu_load}/100  " | bc)
			local cpu_num_all_n=$(( $( getconf _NPROCESSORS_ONLN )-0 ))	
			local cores_used=$(echo "scale=5; ${cpu_load_f}*${cpu_num_all_n} " | bc)
			local cores_used=${cores_used%.*}
			local cores_used=$(( ${cores_used}-0 ))								# numero processori attalmente in uso
			local cpu_num_all=$(( cpu_num_all_n-$cores_used))							# numero totale processori disponibili
			echo $cpu_num_all

			};

memory_available () {
                        ############# ############# ############# ############# ############# ############# #############
                        #############  Stima il numero di processori liberi a partire dal carico della CPU  ############# 
                        ############# ############# ############# ############# ############# ############# #############                  
                        
	
			local memo_vect=( $( free -m ) )
			local memo_total=${memo_vect[7]}	
			local memo_used=${memo_vect[8]}					
			local memo_available=$(( ${memo_total}  - ${memo_used}))	
			echo $memo_available

			};
			
waiting4script () {
                        ############# ############# ############# ############# ############# ############# #############
                        #############	     Aspetta che finiscano n processi relativi ad uno script	    ############# 
                        ############# ############# ############# ############# ############# ############# #############
                         
                        			
			if [ $# -lt 2 ]; then													
			    echo $0: "usage: waiting4script script_name process_number [ global ]"
			    return 1;		    
			fi 
                         
                          			
			local script_name=$1
			local script_number=$2
			local global=$3
			[ -z $global ] && { local global=0; }
			[ $global -ne 1 ]  && { local thisscript="-P $$"; } 
			local stopper=1			
			while [ $stopper -eq 1 ];do
				local pidC_array=( $( pgrep $thisscript -f "${script_name}") ) 
				[ ${#pidC_array[@]} -le $script_number ] && { local stopper=0; }
			done
										
			};
			

waiting4children () {
                        ############# ############# ############# ############# ############# ############# #############
                        #############	  Aspetta che finiscano n processi figli relativi ad uno comando    ############# 
                        ############# ############# ############# ############# ############# ############# #############
                         
                        			
			if [ $# -lt 1 ]; then													
			    echo $0: "usage: waiting4children process_number [ cmd_name ]"
			    return 1;		    
			fi                         
                          			
			local cmd_name=$2
			local script_number=$1
			local stopper=1
			local pidC_num=0
			
			while [ $stopper -eq 1 ];do
					local pidC_array=( $(	pgrep -P $$ -x "${cmd_name}" ) )	
					[ ${#pidC_array[@]} -le $script_number ] && { local stopper=0; }
			done
										
			};


waiting4jobs() {

                max_cores=$1
               jobs_=( $(jobs -p) )
                while [ ${#jobs_[@]} -gt ${max_cores} ]; do jobs_=( $(jobs -p) ); done

}

waiting4func() {
    if [ $# -lt 2 ]; then
        echo "Usage: waiting4func function_name process_number"
        return 1
    fi

    local func_name=$1    # Name of the function to monitor
    local max_processes=$2  # Maximum allowed processes
    local stopper=1        # Loop stopper

    while [ $stopper -eq 1 ]; do
        # Get the list of background jobs for the current shell
        local pidC_array=( $(jobs -p) )

        # Count only those jobs where the function name matches
        local matching_jobs=0
        for pid in "${pidC_array[@]}"; do
            if ps -p "$pid" -o args= | grep -q "${func_name}"; then
                ((matching_jobs++))
            fi
        done

        # If the number of matching jobs is less than the limit, stop waiting
        if [ "$matching_jobs" -le "$max_processes" ]; then
            stopper=0
        else
            sleep 1  # Avoid busy looping
        fi
    done
}




date_ms ()     {
                        ############# ############# ############# ############# ############# ############# #############
                        #############	     		Restituisce la data attuale in ms		    ############# 
                        ############# ############# ############# ############# ############# ############# #############

			echo $(date +%s)
			
			};
elapsed_time () {

                        ############# ############# ############# ############# ############# ############# #############
                        #############	     Stima del tempo di esecuzione dalla data inziale in ( ms )	    ############# 
                        ############# ############# ############# ############# ############# ############# #############
                        
                        START=${1}
                        END=$(date +%s)								# tempo in secondi di fine script
			second=$(echo "scale=5; ${END}-${START} " | bc)				# tempo in secondi dell'esecuzione dello script
			ores=$(echo "scale=5; ${second}/60/60 " | bc)				
			ore=${ores%.*}
			ore=$(( $ore-0 ))							# ore trascorse nell'esecuzione dello script

			minutis=$(echo "scale=5; (${ores}-${ore})*60 " | bc)
			minuti=${minutis%.*}
			minuti=$(( $minuti-0 ))							# minuti trascorsi nell'esecuzione dello script

			secondis=$(echo "scale=5; (${minutis}-${minuti})*60 " | bc)
			secondi=${secondis%.*}							# secondi trascorsi nell'esecuzione dello script


			echo  ${ore}"h" ${minuti}"m" ${secondi}"s"
			
		

			};

setITKthreads () {
			OMP_NUM_THREADS=$1
			ITK_GLOBAL_DEFAULT_NUMBER_OF_THREADS=$1  										# multi-threading ( 4 ANTs)
			export OMP_NUM_THREADS
			export ITK_GLOBAL_DEFAULT_NUMBER_OF_THREADS
			
			}
