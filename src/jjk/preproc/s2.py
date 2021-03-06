#!/usr/bin/env python
#*
#*   RCS data:
#*	$RCSfile: search.py,v $
#*	$Revision: 1.2 $
#*	$Date: 2005/10/03 22:02:18 $
#*
#*   Programmer		: <your name>
#*
#*   Modification History:
#*
#****  C A N A D I A N   A S T R O N O M Y   D A T A   C E N T R E  *****
# Run J-M.'s and Matt's object finding systems... then intersect the 
# results.  


from myTaskError import TaskError

def searchTriples(expnums,ccd):
    """Given a list of exposure numbers, find all the KBOs in that set of exposures"""
    import MOPfits,os 
    import MOPdbaccess
    
    if len(expnums)!=3:
        return(-1)


    ### Some program Constants

    proc_file = open("proc-these-files","w")
    proc_file.write("# Files to be planted and searched\n")
    proc_file.write("#            image fwhm plant\n")
    
    import string
    import os.path
    filenames=[]
    import pyfits
    for expnum in expnums:
    	try: 
            mysql=MOPdbaccess.connect('bucket','cfhls','MYSQL')
            bucket=mysql.cursor()
	except:
            raise TaskError, "mysql failed"
        bucket.execute("SELECT obs_iq_refccd FROM exposure WHERE expnum=%s" , (expnum, ) )
        row=bucket.fetchone()
	mysql.close()
        fwhm=row[0]
        if not fwhm > 0:
            fwhm=1.0

        if int(ccd)<18:
            cutout="[-*,-*]"
        else:
            cutout=None
        filename=MOPfits.adGet(str(expnum)+"p",extno=int(ccd),cutout=cutout)

        if not os.access(filename,os.R_OK):
            raise TaskError, 'adGet Failed'
	    
        filename=os.path.splitext(filename)
        filenames.append(filename[0])
        proc_file.write("%s %f %s \n" % ( filename[0], fwhm/0.183, "no"))

    proc_file.flush()
    proc_file.close()
    
    command="find.pl -p '' -d ./ "

    try:
        os.system(command)
    except:
        raise TaskErorr, "execute find"
    

    file_extens=[
        "cands.comb",
        "measure3.cands.astrom",
        "measure3.WARNING",
        "measure3.astrom.scatter"]
    
    if not os.access("find.OK",os.R_OK):
        raise TaskError, "find failed"
    
        
    astrom=filenames[0]+".measure3.cands.astrom"
    
    if os.access(astrom,os.R_OK):
        return(1)
    else:
        return(0)


if __name__=='__main__':
        ### Must be running as a script
        import optik, sys
        from optik import OptionParser

        parser=OptionParser()
        parser.add_option("--verbose","-v",
                          action="store_true",
                          dest="verbose",
                          help="Provide feedback on what I'm doing")
        parser.add_option("--triple","-t",
                          action="store",
                          type="int",
                          dest="triple",
                          help="Triple to search")
        parser.add_option("--epoch","-e",
                          action="store",
                          default="discovery",
                          help="Epoch to search.  Choose from [discovery|checkup|recovery]"
                          )
        parser.add_option("--block","-b",
                          action="store",
                          dest="block",
                          help="CFEPS block to search")
        parser.add_option("--ccd","-c",
                          action="store",
                          default=-1,
                          type="int",
                          dest="ccd")

        (opt, file_ids)=parser.parse_args()


        import os, shutil, sys
        if os.getenv('_CONDOR_SCRATCH_DIR') != None: os.chdir(os.getenv('_CONDOR_SCRATCH_DIR'))

        import MOPdbaccess
        mysql=MOPdbaccess.connect('cfeps','cfhls',dbSystem='MYSQL')
        cfeps=mysql.cursor()

        if not opt.triple:
            sql="""SELECT distinct(t.id),m.ccd 
            FROM triples t
            JOIN %s d ON t.id=d.triple
            JOIN block_pointing b ON b.pointing=t.pointing
	    JOIN mosaic m
	    LEFT JOIN processing p ON ( p.triple=d.triple AND p.ccd=m.ccd)
            WHERE p.comment IS NULL 
	    AND m.instrument LIKE 'MEGAPRIME' 
	    AND b.block LIKE '%s' order by t.id,m.ccd""" % ( opt.epoch, opt.block, )

            cfeps.execute(sql)
            rows=cfeps.fetchall()
        else:
	    rows=[]
            low=0
            high=36
            if opt.ccd>-1:
                low=opt.ccd
                high=opt.ccd
            for ccd in range(low,high):
                rows.append([opt.triple,ccd])
            
	mysql.close()

        if opt.verbose:
            sys.stderr.write("Searching %d triples \n" % ( len(rows), ) )

        for row in rows:
            triple=row[0]
	    ccd=row[1]
            if opt.verbose:
                sys.stderr.write("Working on "+str(triple)+":"+str(ccd)+"\n")
            comment="searched"
            mysql=MOPdbaccess.connect('cfeps','cfhls',dbSystem='MYSQL')
            cfeps=mysql.cursor()
            sql="SELECT expnum FROM triple_members WHERE triple=%d ORDER BY expnum " % ( triple,)
            cfeps.execute(sql)
            exps=cfeps.fetchall()
            file_ids=[]
            for exp in exps:
                file_ids.append(exp[0])
            if opt.verbose:
                sys.stderr.write("Running find on the files "+str(file_ids))
            wdir=str(triple)+"."+str(ccd)
            os.mkdir(wdir)
            os.chdir(wdir)

	    result=-1
            try:
                result=searchTriples(file_ids,ccd)
            except TaskError, info:
                comment=str(info)
                sql="INSERT INTO processing (triple, status, comment, ccd) VALUES ( %d, %d, '%s', %d ) " % ( triple, result, comment,ccd)
                cfeps.execute(sql)
                mysql.commit()
                
            os.chdir("../")

            if not result>0:
                shutil.rmtree(wdir)
            else:
                result=result+1
            try:
                sql="INSERT INTO processing (triple, status, comment, ccd) VALUES ( %d, %d, '%s', %d ) " % ( triple, result, comment,ccd)
                cfeps.execute(sql)
                mysql.commit()
            except:
                sys.stderr.write("Update failed\n")
                sys.exit(-1)
            
	    mysql.close()
            if opt.verbose:
                sys.stderr.write("Found %d candidates in triple %d on ccd %d\n" % (result, triple, ccd))
