#! /bin/bash

if [ ! -d ZeroPoint ]; then
    mkdir ZeroPoint
fi

#if [ -f GetFiles.sh ]; then
#    \rm -f GetFiles.sh
#fi

#touch GetFiles.sh
#chmod 755 GetFiles.sh

#echo "#! /bin/bash" >> GetFiles.sh
#echo "" >> GetFiles.sh

#for b in 05[AB]Q0*-L5?; do
#for b in 05[AB]Q0*-L5i; do
for b in L5[rs]; do
    cd ${b}
#    for c in chip0[89] chip[123]?; do
    for c in chip??; do
#    for c in chip0[0-7]; do
	cd ${c}
	for f in *; do
if [ -d ${f} ]; then
	    cd ${f}
	    mkdir -p ../../../ZeroPoint/${b}/${c}/${f}
	    i=`ls ??????[op]_??.fits* | head -1`
	    j=`echo ${i} | sed "s/p_/o_/" | sed "s/.fits//" | sed "s/.gz//" | sed "s/.fz//"`
	    k=`echo ${j} | sed "s/o_/p_/"`
	    \rm -f ../../../ZeroPoint/${b}/${c}/${f}/${j}.fits
	    \rm -f ../../../ZeroPoint/${b}/${c}/${f}/${j}.bright.psf
	    if [ -e ${j}.fits ]; then
		ln -s ../../../../${b}/${c}/${f}/${j}.fits ../../../ZeroPoint/${b}/${c}/${f}/${j}.fits
	    elif [ -e ${j}.fits.fz ]; then
		imcopy ${j}.fits.fz[1] ../../../ZeroPoint/${b}/${c}/${f}/${j}.fits
	    elif [ -e ${j}.fits.gz ]; then
		zcat ${j}.fits.gz > ../../../ZeroPoint/${b}/${c}/${f}/${j}.fits
	    elif [ -e ${k}.fits ]; then
		ln -s ../../../../${b}/${c}/${f}/${k}.fits ../../../ZeroPoint/${b}/${c}/${f}/${j}.fits
	    elif [ -e ${k}.fits.fz ]; then
		imcopy ${k}.fits.fz[1] ../../../ZeroPoint/${b}/${c}/${f}/${j}.fits
	    elif [ -e ${k}.fits.gz ]; then
		zcat ${k}.fits.gz > ../../../ZeroPoint/${b}/${c}/${f}/${j}.fits
	    else
		echo "ERROR: files ${b}/${c}/${f}/${j}.fits* and ${b}/${c}/${f}/${k}.fits* do not exist."
#		exit 1
	    fi
#	    l=../../../ZeroPoint/${b}/${c}/${f}/${j}.fits
#	    ci=`gethead CHIPID $l`
#	    co=`echo $ci | awk '{ printf "%2.2d", $1+1}'`
#	    num=`gethead EXPNUM $l`
#	    echo "wget 'http://www.cadc.hia.nrc.gc.ca/authProxy/getData?file_id=${num}p&cutout=[${co}]&archive=CFHT' -O ZeroPoint/${b}/${c}/${f}/${k}.fits.gz" >> ../../../GetFiles.sh
	    cp zeropoint.used ../../../ZeroPoint/${b}/${c}/${f}/
	    if [ -e ${j}.bright.psf ]; then
		ln -s ../../../../${b}/${c}/${f}/${j}.bright.psf ../../../ZeroPoint/${b}/${c}/${f}/${j}.bright.psf
	    elif [ -e ${k}.bright.psf ]; then
		ln -s ../../../../${b}/${c}/${f}/${k}.bright.psf ../../../ZeroPoint/${b}/${c}/${f}/${j}.bright.psf
	    else
		echo "ERROR: files ${b}/${c}/${f}/${j}.bright.psf and ${b}/${c}/${f}/${k}.bright.psf do not exist."
	    fi
	    cd ../
fi
	done
	cd ../
    done
    cd ../
done

exit 0
