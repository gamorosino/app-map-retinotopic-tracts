#! /bin/bash

#########################################################################################################################
#########################################################################################################################
###################                                                                                   ###################
###################	title:	            	  Registration library                                    ###################
###################                                                                                   ###################
###################	description:	Library of functions for registration of brain imaging data       ###################
###################                                                                                   ###################
###################	version:	0.3.5.7.2                                                             ###################
###################	notes:	        Install ANTs, FSL to use this library                             ###################
###################			needs STRlib.sh, FILESlib.sh, IMAGINGlib.sh, CPUlib.sh                    ###################
###################	bash version:   tested on GNU bash, version 4.2.53                                ###################
###################                                                                                   ###################
###################	autor: gamorosino                                                                 ###################
###################     email: g.amorosino@gmail.com                                                  ###################
###################                                                                                   ###################
#########################################################################################################################
#########################################################################################################################
###################                                                                                   ###################
###################	 update: minor bug fixed                                                          ###################	 
###################                                                                                   ###################
#########################################################################################################################
#########################################################################################################################


SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)/"
CPUlib=${SCRIPT_DIR}"/CPUlib.sh"
IMAGINGlib=${SCRIPT_DIR}"/IMAGINGlib.sh"
STRlib=${SCRIPT_DIR}"/STRlib.sh"
FILESlib=${SCRIPT_DIR}"/FILESlib.sh"
source ${STRlib}
source ${FILESlib}
source ${IMAGINGlib}
source ${CPUlib}




registration_brain () {

			

function Usage {
    cat <<USAGE
    

	Usage:

	registration_brain <moving_image.ext> <fixed_image.ext> [ Options ] 

	Main arguments :    
	   moving_image			Image to be registered to the reference image
	   fiexed_image	 		Reference image
	   
	Options:
	   -o, --outputdir 		Specifies the direcotry where registration output files are stored (warp filed, affine mat
	   				and warped image). If not provided creates a folder 'Reg_' in moving_images's directory
	   -s, --settings		Integer that specifies differet settings for antsRegistration: 
	   					1 - very low iterations; just for testing the script 
	   					2 - low iterations; for fast results 
	   					3 - good trade-off between performance and accuracy 
	   					4 - optimus settings (default)
	   --timeseries			Specifes if the moving image is a time-series so the script uses mean volume to estimate 
	   				transformation and applies it to the entire time-series image.
	   --no-transl			Disable transaltion transformation stage
	   --no-rigid			Disable rigid transformation stage
	   --no-affine			Disable affine transformation stage
	   --no-nonlin			Disable non-linear transformation stage
	   -i, --interp			Type of interpolation (linear - NN - Bspline - ML); default is NN.

	   -c, --CPUs           	Number of cores for multithreading operations (defalt 2). You could set it with string 
	   				'auto' so the script automatically uses the maximum number of free cores avaliable
	Advance options:
	   -x, --masks 			Image masks to limit voxels considered by the metric:
					[fixedImageMask,movingImageMask]   
	   -m, --metrics 		Specifies lists of metrics for non-linear stage (like ANTs way):
					[name_of_the_metric1[fixed_image1,moving_image1,weight1],name_of_metric2[fixed_image2,moving_image1,weight2 ],...]   
	   -w, --winsorize			Winsorize data based on specified quantiles:
					[lowerQuantile,upperQuantile] 	   
	   -g, --res-def		This option allows the user to restrict the optimization of the displacement field on a 
					per-component basis (PxQxR). Useful in case of epi-correction using non-linear 
					transformation (e.g. 1x1x0.2)    
	Other arguments:

	   -h, --help          		Show this help message
	   -v, --no-verbose		Turn off verbose output 
	  
	Example:

	registration_brain moving_image.nii.gz fixed_mask.nii.gz -s 3 -c 'auto' --no-transl
	registration_brain moving_image.nii.gz fixed_mask.nii.gz --masks [fixedImageMask.nii.gz,movingImageMask.nii.gz]

USAGE
    return 1
}

		#########################################################################################################################
		###################	           			Input Parsing				      ###################
		#########################################################################################################################

		local m=${1}
		local m_reg=${m}
		local f=${2}
		local nargs=$#

		#default values
		local transl=1
		local rigid=1
		local affine=1
		local nonlin=1
		local timeseries=0
		local interp=Bspline
		local verbose_=1

		# Provide output for Help
		if [[ "$1" == "-h" || "$1" == "--help" ]];
		  then
		    Usage >&2
		  fi

		# As long as there is at least one more argument, keep looping
		while [[ $# -gt 0 ]]; do
		    key="$3"
		    case "$key" in
		
			-h|--help)        
			Usage >&2
		      	return 0
			;;
			-o|--outputdir)
			shift
			local regPath="${3}"
			let nargs=$nargs-1
			;;
			--outputdir=*)
			local regPath="${key#*=}"
			;;
			-c|--CPUs)
			shift 
			local cpu_num="$3"
			let nargs=$nargs-1
			;;
			--CPUs=*)
			local cpu_num="${key#*=}"
			;;
			-s|--settings)
			shift 
			local settings="$3"
			let nargs=$nargs-1
			;;
			--settings=*)
			local settings="${key#*=}"
			;;
			-i|--interp)
			shift 
			local interp="$3"
			let nargs=$nargs-1
			;;
			--interp=*)
			local interp="${key#*=}"
			;;
			-x|--masks)
			shift 
			local masks="$3"
			let nargs=$nargs-1
			;;
			--masks=*)
			local masks="${key#*=}"
			;;
			-m|--metrics)
			shift 
			local metrics="$3"
			let nargs=$nargs-1
			;;
			--metrics=*)
			local metrics="${key#*=}"
			;;			
			-w|--winsorize)
			shift 
			local winsorize="$3"
			let nargs=$nargs-1
			;;
			--winsorize=*)
			local winsorize="${key#*=}"
			;;
			-g|--res-def)
			shift 
			local resdef="$3"
			let nargs=$nargs-1
			;;
			--res-def=*)
			local resdef="${key#*=}"
			;;
			--timeseries)        
			local timeseries=1	
			;;
			--no-transl)        
			local transl=0	
			;;
			--no-rigid)        
			local rigid=0	
			;;       
			--no-affine)        
			local affine=0	
			;;       
			--no-nonlin)        
			local nonlin=0	
			;;
			-v|--no-verbose)        
			local verbose_=0
			;;
		       
		
			*)
			# Do whatever you want with extra options
			[ -z $key ] || { echo "Unknown option '$key'";} 
			;;
		    esac
		    # Shift after checking all the cases to get the next option
		    shift
		done

		

		if [ $nargs -lt 2 ]; then												# usage 
							
			 Usage >&2; return 1
		fi

		[ -z ${regPath} ] && { local regPath=$(dirname "${m}")"/Reg_"; }
		mkdir -p ${regPath};
		[ -z ${settings} ] && { local settings=4;}
		[ "${cpu_num}" == "auto" ] && { local cpu_num=$( CPUs_available ); }
		[ -z ${cpu_num} ] && { local cpu_num=2;}

		echo "regPath: " $regPath
		echo "cpu_num: " $cpu_num
		echo "settings: " $settings

		setITKthreads $cpu_num 													# multi-threading
		echo "number of cores for multithreading: " $ITK_GLOBAL_DEFAULT_NUMBER_OF_THREADS 

		dimf=$( imm_dim $f )
		echo "fixed image dimension: " $dimf
		dimm=$( imm_dim $m )
		echo "moving image dimension: " $dimm

		if [ $timeseries -eq 1 ] ; then

			[ $dimm -eq 4 ] && { m_mean=$( remove_ext ${m} )"_mean.nii.gz"; fslmaths ${m} -Tmean ${m_mean} ; m=${m_mean}; }\
					|| { echo "wrong moving image dimension"; return 1; }
			[ $dimf -eq 4 ] && { f_mean=$( remove_ext ${f} )"_mean.nii.gz"; fslmaths ${f} -Tmean ${f_mean} ; f=${f_mean}; }\
					|| { [ $dimf -eq 3 ] || { echo "wrong fixed image dimension"; return 1;}  }
			dim=3

		else

			[ $dimm -ne $dimf ] && { echo "WARING: the dimension of the images is different "; }
			dim=$dimf 

		fi

		#########################################################################################################################
		###################                                         MAIN                                      ###################
		#########################################################################################################################

		#thresold=1.e-6
		local thresold=1.e-8
		#diffeo=BSplineSyN[.1,26,0,3]
		local diffeo=SyN[0.25]													# tipologia di 
		local reg=antsRegistration           												# funzione di registrazione di ants  
		local extem=$( fextension $m_reg )
		if ( [ "${extem}" == "gz" ] || [ "${extem}" == "nii" ] ); then
			local nm2=$( basename $( remove_ext  $m_reg ) )
		else
			local nm2=$( fbasename $m_reg ) 
		fi
																	# prefisso dei file di output

		case $settings in
			     "1")
			  echo "one level"
				  its=10000x0x0
				  percentage=0.1
				  syn="100x0x0,0,5" 
				  sigma=1x0.5x0vox
				  shrink=4x2x1
				  sigma_lin=4x2x1vox
				  shrink0=6x4x2
				  shrink_lin=3x2x1
				  #settings=onelevel 		
			  ;;
		    	 "2")
			  echo "two levels"
				  its=10000x10000x0
				  percentage=0.3
				  syn="100x100x0,-0.01,5"
				  sigma=1x0.5x0vox
				  shrink=4x2x1
				  sigma_lin=4x2x1vox
				  shrink0=6x4x2
				  shrink_lin=3x2x1
				  #settings=twolevels         

			  ;;
		    	 "3")
			  echo "three levels"
				  its=10000x111110x11110
				  percentage=0.3
				  syn="100x100x30,-0.01,5"
				  sigma=1x0.5x0vox
				  shrink=4x2x1
				  sigma_lin=4x2x1vox
				  shrink0=6x4x2
				  shrink_lin=3x2x1
				  #settings=threelevels         

			  ;;
		    	 "4")
			  echo "fourlevels"
				  its=10000x10000x10000
				  percentage=0.3
				  syn="100x80x50x20,${thresold},10"
				  sigma=2x1x0.5x0vox
				  shrink=8x4x2x1
				  sigma_lin=4x2x1vox
				  shrink0=6x4x2
				  shrink_lin=3x2x1
				  #settings=fourlevels
			  ;;
			  "4+")
			  echo "fourlevels(all)"
				  its=10000x10000x10000x10000
				  percentage=0.3
				  syn="100x80x50x20,${thresold},10"
				  sigma=2x1x0.5x0vox
				  shrink=8x4x2x1
				  sigma_lin=8x4x2x1vox
				  shrink0=12x6x4x2
				  shrink_lin=6x3x2x1
				  #settings=fourlevels
			  ;;           
		     	  *)
			  echo "setting errato"
					return 1
			  ;;
		esac

		if [ ${nonlin} -eq 1 ]; then
			if [ -z "${metrics}" ]; then

				local metrics="mattes[  $f, $m , 0.5 , 32 ] -m cc[  $f, $m , 0.5 , 4 ]";
				echo "use default metrics (for non-linear stage): "
				echo " "${metrics}	

			else
				metrics=${metrics//' '/''}
				local metrics=${metrics//'],'/'] -m '}
				local metrics=${metrics:1:${#metrics}-2}	
				echo "use metrics (for non-linear stage): "
				echo " "${metrics}	
			fi
			
			local stage3="-m ${metrics}   -c [ $syn ]  -t $diffeo -s $sigma -f $shrink -l 1 -u 1 -z 1 -u 1"

			[ -n "${resdef}" ] && { local stage3="${stage3}"" -g ${resdef} "; }

		fi

		local stage0="-m mattes[  $f, $m , 1 , 32, regular, $percentage ] -t translation[ 0.1 ] -c [$its,$thresold,20] -u 1 -s $shrink_lin -f $shrink0 -l 1"
		local stage1="-m mattes[  $f, $m , 1 , 32, regular, $percentage ] -t rigid[ 0.1 ]       -c [$its,$thresold,20] -u 1 -s $shrink_lin -f $shrink_lin -l 1"
		local stage2="-m mattes[  $f, $m , 1 , 32, regular, $percentage ] -t affine[ 0.1 ]      -c [$its,$thresold,20] -u 1 -s $shrink_lin -f $shrink_lin -l 1"


		[ "${interp}" == "linear" ]  && { interp="Linear"; }
		[ "${interp}" == "NN" 	]  && { interp="NearestNeighbor "; }
		[ "${interp}" == "BSline" ]  && { interp="BSpline ";}
		[ "${interp}" == "ML" 	]  && { interp="MultiLabel ";}
		
		

		[ ${transl} -eq 0 ]  && { stage0='';} || { diffeopost="trasl"; }
		[ ${rigid}  -eq 0 ]  && { stage1='';} || { diffeopost="rigid"; }
		[ ${affine} -eq 0 ]  && { stage2='';} || { diffeopost="affine"; }
		[ ${nonlin} -eq 0 ]  && { stage3='';} || { diffeopost=$( echo $diffeo | cut -d "[" -f1 );}

		local reg_version_v=( $( antsRegistration --version ) )
		reg_version=${reg_version_v[3]}

		[ "${reg_version}" == "2.1.0-g78931" ] || { local reg_command1=" -v $verbose_ "; }

		if [ -n "${masks}" ]; then
			local reg_command0=" -x ${masks} "; 
			local stage0=${stage0}" ""-x [NULL,NULL]";
			local stage1=${stage1}" ""-x [NULL,NULL]";
			local stage2=${stage2}" ""-x [NULL,NULL]";
			local stage3=${stage3}" ""${reg_command0}";
		fi

		[ -z ${winsorize} ] ||  { ref_command_w="-w "${winsorize}; }
	
		nm=${nm2}_${diffeopost};
		set -f
		$reg -d $dim -r [ $f, $m ,1] --float 1 $reg_command1 \
							     $stage0\
							     $stage1\
							     $stage2\
							     $stage3\
							     $ref_command_w \
							      -o [${regPath}/${nm},${regPath}/${nm}_diff.nii.gz,${regPath}/${nm}_inv.nii.gz]
		set +f

		( [ $dimm -eq 4 ] && [ $timeseries -eq 1 ] ) && { local input_type=3; } || { local input_type=0; }

		if [ ${nonlin} -eq 1 ]; then

			antsApplyTransforms -d $dim -i $m_reg -r $f  -t ${regPath}"/"${nm}1Warp.nii.gz -t ${regPath}"/"${nm}0GenericAffine.mat\
								-o ${regPath}"/"${nm}_warped.nii.gz $reg_command1 -n $interp -e $input_type 	
		else
			antsApplyTransforms -d $dim -i $m_reg -r $f  -t ${regPath}"/"${nm}0GenericAffine.mat -o ${regPath}"/"${nm}_warped.nii.gz $reg_command1 -n $interp -e $input_type 
	

		fi						
		};

warp_image () {


function Usage {
    cat <<USAGE
    

	Usage:

	warp_image <moving_image.ext> <image_to_warp.ext> [ Options ]

	Main arguments :
	    
	   moving_image			Image in the space where the reference image is warped
	   image_to_warp 		Image to be warped to out_image space

	Optional arguments:

	   -r, --reg-dir 		Specifies the direcotry where registration output files are stored (warp filed, affine mat 
	   				and wapred image). If not provided the script expects to find 'Reg_' folder in out_image's
	   			        directory
	   -t, --reg-transf	 	specifies last transformation stage used in the registration step (trasl - rigid - affine 
	   				- BSplineSyN - SyN); default is SyN. 
	   -o, --out-image		Output warped image. If not provided the script creates a folder 'Warped_' in moving_image's 
	   				directory and store the warped mask in.
	   -i, --interp			Type of interpolation (linear - NN - Bspline - ML); default is NN.
	   
	   -f, warp-forward 		Apply warp from moving image space to reference space (assuming image_to_warp in moving space)
	   
	   -m, --ref-image		Specifies reference image that defines the spacing, origin, size, and direction of the 
					output warped image (default is moving_image)

	   --timeseries			Specifies if out_image is a timeseries
	   
	Other arguments:

	   -h, --help          		Show this help message
	   -v, --no-verbose		Turn off verbose output
	  
	Example:

	warp_image moving_image.nii.gz ref_image.nii.gz -t "BSplineSyN"



USAGE
    return 1
}

		#########################################################################################################################
		###################	           			Input Parsing				      ###################
		#########################################################################################################################


		local image_out=${1}
		local mask_rif=${2}
		local nargs=$#

		#default
		local timeseries=0
		local multiimage=0
		local interpolation='NN'
		local useInverse=1
		local verbose_=1

		# Provide output for Help
		if [[ "$1" == "-h" || "$1" == "--help" ]];
		  then
		    Usage >&2
		  fi

		# As long as there is at least one more argument, keep looping
		while [[ $# -gt 0 ]]; do
		    key="$3"
		    case "$key" in
		
			-h|--help)        
			Usage >&2
		      	return 0
			;;    
			-t|--reg-transf)
			shift
			local diffeopost=${3}
			let nargs=$nargs-1
			;;
			--reg-transf=*)
			local diffeopost="${key#*=}"
			;;        
			-o|--out-image)
			shift 
			local mask_out="$3"
			let nargs=$nargs-1
			;;
			--out-image=*)
			local mask_out="${key#*=}"
			;;
			-r|--reg-dir)
			shift
			local regPath="${3}"
			let nargs=$nargs-1
			;;
			--reg-dir=*)
			local regPath="${key#*=}"
			;;
			-i|--interp)
			shift
			local interpolation=${3}
			let nargs=$nargs-1
			;;
			--interp=*)
			local inteprolation="${key#*=}"
			;;
			--timeseries)        
			local timeseries=1
			;;
			-f|--warp-forward)        
			local useInverse=0		
			;;
			-m|--ref-image)
			shift 
			local ref_image="$3"
			let nargs=$nargs-1
			;;
			--ref-image=*)
			local ref_image="${key#*=}"
			;;
			-v|--no-verbose)        
			local verbose_=0
			;;
			*)
			# Do whatever you want with extra options
			[ -z $key ] || { echo "Unknown option '$key'";} 
			;;
		    esac
		    # Shift after checking all the cases to get the next option
		    shift
		done

		if [ $nargs -lt 2 ]; then							# usage dello script
							
			 Usage >&2; return 1
		fi

		default_reg_dir="Reg_"

		[ -z $diffeopost ] && { local diffeopost="SyN"; }  


		#########################################################################################################################
		###################	           			MAIN					      ###################
		#########################################################################################################################

		local extem=$( fextension $mask_rif )
		if ( [ "${extem}" == "gz" ] || [ "${extem}" == "nii" ] ); then
			local mask_name=$( basename $( remove_ext  $mask_rif ) )
		else
			local mask_name=$( fbasename $mask_rif ) 
		fi

		local extem=$( fextension $image_out )
		if ( [ "${extem}" == "gz" ] || [ "${extem}" == "nii" ] ); then
			local Image_name=$( basename $( remove_ext  $image_out ) )
		else
			local Image_name=$( fbasename $image_out ) 
		fi

		nm=${Image_name}_${diffeopost};

		if [ -z $mask_out ]; then
			local warpPath=$(dirname "${image_out}")"/Warped_"; 
			local mask_out=${warpPath}/${mask_name}_${nm}_warped.nii.gz; 
			mkdir -p $warpPath; 
		else
			local warpPath=$(dirname "${mask_out}");
			mkdir -p ${warpPath} 
			

		fi		

		[ -z $regPath ] && { local regPath=$( dirname $image_out )"/${default_reg_dir}/"; }
		 
		local campo=${regPath}"/"${nm}1InverseWarp.nii.gz
		local dcampo=${regPath}"/"${nm}1Warp.nii.gz
		local mat_aff=${regPath}"/"${nm}0GenericAffine.mat

		[ "${interpolation}" == "linear" ]  && { local warp_command0=""; local apply_command0=""; }
		[ "${interpolation}" == "NN" 	]  && { local warp_command0="--use-NN"; local apply_command0=" --interpolation NearestNeighbor "; }
		[ "${interpolation}" == "BSline" ]  && { local warp_command0="--use-BSpline"; local apply_command0=" --interpolation BSpline ";}
		[ "${interpolation}" == "ML" 	]  && { local warp_command0="--use-ML 0.5x0.5x0.5vox"; local apply_command0=" --interpolation MultiLabel ";}

		[  ${useInverse} -eq 1 ] && { local warp_commad1=' -i ';  }
		
		[  ${useInverse} -eq 0 ] && { local campo=${dcampo};  }

		[ $timeseries -eq 1 ] && { m_mean=$( remove_ext ${image_out}  )"_mean.nii.gz"; fslmaths ${image_out} -Tmean ${m_mean} ; image_out=${m_mean};}

		warp_version=$( which antsApplyTransforms )
		mask_size=( $( imm_size ${mask_rif} "space" ) )
		[ -z ${mask_size[3]} ] && { local warp_type=0; } || { local warp_type=3; }

		if [ -z ${ref_image} ]; then
		
			[ ${useInverse} -eq 1 ] || { image_out=${regPath}"/"${nm}"_warped.nii.gz"; }

		else

			image_out=${ref_image}

		fi

		if [ -z ${warp_version} ]; then 		
	
	
	
			if [ -z ${mask_size[3]} ]; then

				if ( [ "$diffeopost" == "SyN" ] || [ $diffeopost == "BSplineSyN" ] ); then
		
					WarpImageMultiTransform 3 ${mask_rif} ${mask_out}  -R ${image_out}  $warp_command0 ${warp_commad1} ${mat_aff}  ${campo}  
				else
					WarpImageMultiTransform 3 ${mask_rif} ${mask_out}  -R ${image_out}  $warp_command0 ${warp_commad1} ${mat_aff}  

				fi
			else
	
			#TODO: fare warp di mask 4D nel caso di versione vecchia
			echo "command not yet implemented for old ANTs version"


			fi
		else
				local reg_version_v=( $( antsRegistration --version ) )
				local reg_version=${reg_version_v[3]}
				[ "${reg_version}" == "2.1.0-g78931" ] || { local reg_command1=" -v $verbose_ "; }

			if ( [ "$diffeopost" == "SyN" ] || [ $diffeopost == "BSplineSyN" ] ); then

		
				antsApplyTransforms -d 3  -r ${image_out} -o ${mask_out}  -i ${mask_rif} -t ${campo} -t [${mat_aff},${useInverse}]   $apply_command0 -e ${warp_type} $reg_command1
			else				
				antsApplyTransforms -d 3 -r ${image_out} -o ${mask_out}  -i ${mask_rif}  -t [${mat_aff},${useInverse}]   $apply_command0 -e ${warp_type} $reg_command1

			fi



		fi

		};


mask_cleaning () { 

		if [ $# -lt 1 ]; then
							# usage dello script							
			    echo $0: "usage: mask_cleaning <input_mask.ext> [<output_mask.ext>]"
			    return 1;		    
		fi 

		#########################################################################################################################
		###################	           		    Input Parsing 				      ###################
		#########################################################################################################################

		local mask_out=$1
		local fileclean_n=$2

		#########################################################################################################################
		###################	           			MAIN					      ###################
		#########################################################################################################################
		
		local direct=$(dirname "${mask_out}");
		local max=$( imm_max $mask_out )
		local order_true=${#max}
		local nmc=$( fbasename ${mask_out} );
		local file=${nmc}"_mul.nii.gz"
		local multy=1000
		local dim=$( imm_dim $mask_out )
		ImageMath $dim ${file} m ${mask_out} $multy
		max=$( imm_max $file )
		local order=${#max}
		order=$(echo "scale=9; ${order}-${order_true}" | bc)
		ord=$(echo "scale=9; 10^${order}" | bc)
		local N=$(echo "scale=0; ${max}/${ord}" | bc)
		echo "maximum number of labels: "$N
		fileclean_f=""
		[ -z ${fileclean_n} ] && { fileclean_n=${direct}/${nmc}"_clean.nii.gz"; }

		for (( j=1; j<=$N; j++ ));
				do

				fileclean=${direct}/${nmc}_clean${j}.nii.gz
				thr=$(echo "scale=9; ${ord}*${j}" | bc)
				ThresholdImage $dim $file $fileclean ${thr} ${thr}
				ImageMath $dim $fileclean m $fileclean ${thr}
				if [ $j -eq 1 ]; then
		
					fileclean_f=$fileclean
				else
					ImageMath $dim $fileclean_f + $fileclean $fileclean_f
					rm $fileclean		
				fi;

		done;
	
		#mv $fileclean_f $file                                        					# replace input

		mv $fileclean_f $fileclean_n

		ImageMath $dim $fileclean_n / $fileclean_n $multy

		};		


reg_n_warp_brain () { 


function Usage {
    cat <<USAGE
    

	Usage:

	reg_n_warp_brain <moving_image.ext> <fixed_image.ext> <image_to_warp.ext> [ Options ]

	Main arguments :
	    
	   moving_image			Image to be registered to the reference image
	   fiexed_image	 		Reference image
	   image_to_warp		Image to be warped to moving_image space

	General Options:

	   -c, --CPUs           	Number of cores for multithreading operations (defalt 2). You could set it with string 
	   				'auto' so the script automatically uses the maximum number of free cores avaliable  
	Registration Options:

	   -r, --reg-dir		Specifies the direcotry where registration output files are stored (warp filed, affine mat
	   				and warped image). If not provided creates a folder 'Reg_' in moving_images's directory
	   -s, --settings		Integer that specifies differet settings for antsRegistration: 
	   					1 - very low iterations; just for testing the script 
	   					2 - low iterations; for fast results 
	   					3 - good trade-off between performance and accuracy 
	   					4 - optimus settings (default)
	   -x, --reg-masks		[fixedImageMask,movingImageMask] Image masks to limit voxels considered by the metric.

	   -m, --reg-metrics 		Specifies lists of metrics for non-linear stage (like ANTs way):
					[name_of_the_metric1[fixed_image1,moving_image1,weight1],name_of_metric2[fixed_image2,moving_image1,weight2 ],...]
	   -w, --winsorize		Winsorize data based on specified quantiles:
					[lowerQuantile,upperQuantile] 
	   -g, --res-def		This option allows the user to restrict the optimization of the displacement field on a 
					per-component basis (PxQxR). Useful in case of epi-correction using non-linear 
					transformation (e.g. 1x1x0.2)  
	   -p, --reg-interp		Type of interpolation in registration stage (linear - NN - Bspline - ML) ; default is NN.

	   --timeseries			Specifes if the moving image is a time-series so the script uses mean volume to estimate 
	   				transformation and applies it to the entire time-series image.
	   --no-transl			Disable transaltion transformation stage
	   --no-rigid			Disable rigid transformation stage
	   --no-affine			Disable affine transformation stage
	   --no-nonlin			Disable non-linear transformation stage
	      
	Warp Options:

	   -o, --out-image		Output warped mask. If not provided the script creates a folder 'Warped_' in 
	   				image_out's directory and store the warped mask in.
	   -i, --warp-interp		Type of interpolation in warp stage (linear - NN - Bspline - ML) ; default is NN.
	
	   -f, --warp-forward		Apply warp from moving image space to reference space (assuming image_to_warp in moving space)
	   
	   -l, --clean-mask		Cleaning warped mask from rounding errors. 

	Other arguments:

	   -h, --help          		Show this help message
	   -v, --no-verbose		Turn off verbose output

	Example:

	reg_n_warp_brain  moving_image.nii.gz fixed_mask.nii.gz ref_mask.nii.gz -s 3 -c 'auto' --no-nonlin
	reg_n_warp_brain  moving_image.nii fixed_mask.nii mask.nii -m [cc[fixed_mask.nii,moving_image.nii],MI[fix_wm.nii,moving_wm.nii]]


USAGE
    return 1
}


	
			
		START=$(date +%s)
		#########################################################################################################################
		###################	           			Input Parsing				      ###################
		#########################################################################################################################

		local m=${1}
		local m_reg=${m}
		local f=${2}
		local mask_rif=${3}
		local nargs=$#

		#default values
		local transl=1
		local rigid=1
		local affine=1
		local nonlin=1
		local timeseries=0
		local settings=4
		local clean_mask=0
		local interpolation='NN'
		local multiimage=0
		local reginterp=Bspline
		local verbose_=1

		# Provide output for Help
		if [[ "$1" == "-h" || "$1" == "--help" ]];
		  then
		    Usage >&2
		  fi

		# As long as there is at least one more argument, keep looping
		while [[ $# -gt 0 ]]; do
		    key="$4"
		    case "$key" in
		
			-h|--help)        
			Usage >&2
		      	return 0
			;;
			-r|--reg-dir)
			shift
			local regPath="${4}"
			let nargs=$nargs-1
			;;
			--reg-dir=*)
			local regPath="${key#*=}"
			;;
			-x|--reg-masks)
			shift 
			local masks="${4}"
			let nargs=$nargs-1
			;;
			--reg-masks=*)
			local masks="${key#*=}"
			;;
			-m|--reg-metrics)
			shift 
			local metrics="$4"
			let nargs=$nargs-1
			;;
			--reg-metrics=*)
			local metrics="${key#*=}"
			;;
			-p|--reg-interp)
			shift 
			local reginterp="$4"
			let nargs=$nargs-1
			;;
			--reg-interp=*)
			local reginterp="${key#*=}"
			;;
			-w|--winsorize)
			shift 
			local winsorize="$4"
			let nargs=$nargs-1
			;;
			--winsorize=*)
			local winsorize="${key#*=}"
			;;
			-g|--res-def)
			local resdef="$4"
			let nargs=$nargs-1
			;;
			--res-def=*)
			local resdef="${key#*=}"
			;;	
			-c|--CPUs)
			shift 
			local cpu_num="$4"
			let nargs=$nargs-1
			;;
			--CPUs=*)
			local cpu_num="${key#*=}"
			;;
			-s|--settings)
			shift 
			local settings="$4"
			let nargs=$nargs-1
			;;
			--settings=*)
			local settings="${key#*=}"
			;;
			--timeseries)        
			local timeseries=1	
			;;
			--no-transl)        
			local transl=0	
			;;
			--no-rigid)        
			local rigid=0	
			;;       
			--no-affine)        
			local affine=0	
			;;       
			--no-nonlin)        
			local nonlin=0	
			;;
			--clean-mask)        
			local clean_mask=1	
			;;
			-o|--out-image)
			shift 
			local mask_out="$4"
			let nargs=$nargs-1
			;;
			--out-image=*)
			local mask_out="${key#*=}"
			;;
			-i|--warp-interp)
			shift 
			local interpolation="$4"
			let nargs=$nargs-1
			;;
			--warp-interp=*)
			local interpolation="${key#*=}"
			;;
			-f|--warp-forward)        
			local warp_command1=' -f '
			;;
			-4D|--timeseries)        
			local multiimage=1	
			;;        
			-v|--no-verbose)        
			local verbose_=0
			;;
			*)
			# Do whatever you want with extra options
			[ -z $key ] || { echo "Unknown option '$key'";} 
			;;
		    esac
		    # Shift after checking all the cases to get the next option
		    shift
		done


		
		if [ $nargs -lt 3 ]; then												# usage dello script
							
			 Usage >&2; return 1
		fi

																# reference mask on fixed space
		inputPath=$(dirname "${m}")
		[ -z $regPath ] && { local regPath=${inputPath}"/Reg_/"; }
		mkdir -p ${regPath}	
		[ -z "$cpu_num" ] && { local cpu_num=2; }


		local reg_version_v=( $( antsRegistration --version ) )
		reg_version=${reg_version_v[3]}

		if [ "${reg_version}" != "2.1.0-g78931" ]; then

			[ $verbose_ -eq 0 ] && { local reg_commandV=" -v "; }

		fi
	
		#########################################################################################################################
		###################		            REGISTRAZIONE DELLE IMMAGINI			      ###################
		#########################################################################################################################
		
		

		[ $timeseries -eq 1 ] 	&& 	{ reg_command0="--timeseries"; } 
		[ -n "${masks}" ] 	&& 	{ local reg_command5=" -x ${masks} "; }
		[ ${transl} -eq 1 ]  	&& 	{ local transf="trasl";local reg_command1="  ";} || {	local reg_command1=" --no-transl ";}
		[ ${rigid}  -eq 1 ]  	&& 	{ local transf="rigid";local reg_command2="  ";} || {	local reg_command2=" --no-rigid  ";}
		[ ${affine} -eq 1 ]  	&& 	{ local transf="affine";local reg_command3="  ";} || {  local reg_command3=" --no-affine ";}
		[ ${nonlin} -eq 1 ]  	&& 	{ local transf="SyN";local reg_command4="  ";	} || {  local reg_command4=" --no-nonlin ";}
		[ -z "${metrics}" ] 	|| 	{ local reg_command6=" --metrics ""${metrics}" ; } 
		[ -z "${winsorize}" ] 	|| 	{ local reg_command7=" -w ""${winsorize}" ; } 
		[ -z "${resdef}" ]	||	{ local reg_command8=" -g ""${resdef}" ; }
		registration_brain $m $f --outputdir $regPath -c $cpu_num -s $settings -i $reginterp 	$reg_command0 \
										      			$reg_command1 \
										      			$reg_command2 \
										      			$reg_command3 \
										      			$reg_command4 \
										      			$reg_command5 \
										      			$reg_command6 \
										      			$reg_command7 \
										      			$reg_command8 \
													$reg_commandV
		echo
		echo ":::::::::::::::::::::::::::::::::::::::::::::::::::::::::::::::::::::::::::::::::::::::::::::::::::::::::::::::"
		echo "::::::::::::::::            Registration of $(basename ${m}) done            :::::::::::::::::::"
		echo ":::::::::::::::::::::::::::::::::::::::::::::::::::::::::::::::::::::::::::::::::::::::::::::::::::::::::::::::"
		echo

		
		#########################################################################################################################
		###################		            WARP DELLA MASCHERA DI RIFERIMENTO			      ###################
		#########################################################################################################################

		local warpPath=${inputPath}"/Warped_/"
		mkdir -p ${warpPath}
		local Image_name=$( fbasename ${m} );
		local nm=${Image_name}_${transf}
		local mask_name=$( fbasename ${mask_rif} );
		local mask_out_n=${warpPath}/${mask_name}_${nm}_warped.nii.gz

		[ -z $mask_out ] && { local mask_out=$mask_out_n; }

		[ ${multiimage} -eq 1 ] && { local warp_command0="-4D" ;}
		 
		[ -z ${warp_command1} ] || { local warp_command2=" --ref-image "${f} ; }

		warp_image $m $mask_rif --reg-dir $regPath --out-image $mask_out --reg-transf ${transf} --interp ${interpolation} \
							${reg_command0} ${warp_command0} ${warp_command1} ${warp_command2} \
$reg_commandV


		echo
		echo "::::::::::::::::::::::::::::::::::::::::::::::::::::::::::::::::::::::::::::::::::::::::"
		echo "::::::::::::::::            Warp of "$( basename ${mask_rif} )" done            :::::::::::::::::::"
		echo "::::::::::::::::::::::::::::::::::::::::::::::::::::::::::::::::::::::::::::::::::::::::"
		echo	


		#########################################################################################################################
		###################		            PULIZIA ERRORI DA ARROTONDAMENTO			      ###################
		#########################################################################################################################

		if [ $clean_mask -eq 1 ]; then
		
			mask_cleaning $mask_out
	
			echo
			echo "::::::::::::::::::::::::::::::::::::::::::::::::::::::::::::::::::::::::::::::::::::::::"
			echo "::::::::::::::::           	mask cleaning done  	           :::::::::::::::::::"
			echo "::::::::::::::::::::::::::::::::::::::::::::::::::::::::::::::::::::::::::::::::::::::::"
			echo	

		fi

		#########################################################################################################################
		###################	           		Stima del tempo di esecuzione			      ###################
		#########################################################################################################################



		END=$(date +%s)
		second=$(echo "scale=5; ${END}-${START} " | bc)
		ores=$(echo "scale=5; ${second}/60/60 " | bc)
		ore=${ores%.*}
		ore=$(( $ore-0 ))

		minutis=$(echo "scale=5; (${ores}-${ore})*60 " | bc)
		minuti=${minutis%.*}
		minuti=$(( $minuti-0 ))

		secondis=$(echo "scale=5; (${minutis}-${minuti})*60 " | bc)
		secondi=${secondis%.*}
		echo
		echo
		echo ":::::::::::::::::::::::::::::::::::::::::::::::::::::::::::::::::::::::::::::::::"
		echo "::::::::::: TEMPO DI ESECUZIONE : ${ore} ore ${minuti} minuti ${secondi} secondi :::::::::::::"
		echo ":::::::::::::::::::::::::::::::::::::::::::::::::::::::::::::::::::::::::::::::::"
		echo
		echo

		};
