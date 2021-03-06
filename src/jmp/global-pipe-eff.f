C -*-compile-command: "g77 -O3 -o ../../bin/LINUX/global-pipe-eff global-pipe-eff.f -L../../lib/LINUX -ljmp"; -*-

      implicit none

      integer*4
     $  i, i_mag, j, n_max, lp, narg, iargc, i2, i1, ld, lf

      parameter
     $  (n_max = 3000)

      real*4
     $  mag, fx, fy, fra, mag_min, mag_step, hfa(n_max), hfo(n_max),
     $  frac, fangle, sigma, jmpfo(n_max), mattfo(n_max)

      character
     $  arg*80, dirname*200, filename*100, listname*80, pref*80,
     $  line*200

      logical
     $  help, finished, no_s, no_m, no_f


c Create a file for later error handling

      open (unit=1, file='global-pipe-eff.FAILED', status='unknown')
      write (1, *) ' '
      close (1)

      do j = 1, 80
         pref(j:j) = char(0)
      end do
      narg = iargc()
      no_f = .true.
      no_m = .true.
      no_s = .true.
      help = (narg .ne. 6)
      i = 1
 90   continue
      if (i .le. narg) then
         call getarg (i, arg)
         if (arg(1:2) .eq. '-f') then
            i = i + 1
            call getarg (i, listname)
            no_f = .false.
         else if (arg(1:2) .eq. '-s') then
            i = i + 1
            call getarg (i, arg)
            read (arg, *) mag_step
            no_s = .false.
         else if (arg(1:2) .eq. '-m') then
            i = i + 1
            call getarg (i, arg)
            read (arg, *) mag_min
            no_m = .false.
         else if ((arg(1:2) .eq. '-h') .or. (arg(1:2) .eq. '-?')) then
            i = narg + 1
            help = .true.
         end if
         i = i + 1
         goto 90
      end if

      help = help .or. no_f .or. no_m .or. no_s

      j = 1
      do i = 0, narg
         call getarg (i, arg)
         call read_file_name (arg, i1, i2, finished, 80)
         line(j:j+i2-i1) = arg(i1:i2)
         j = j + i2 - i1 + 1
         line(j:j) = ' '
         j = j + 1
      end do
      write (6, *) line(1:j-1)

      open (unit=1, file='global-pipe-eff.FAILED', status='unknown')
      write (1, *) line(1:j-1)
      close (1)

      if (help) then
         write (6, *) 'Usage: global-pipe-eff -f <file list>'
     $        //' -m <min mag> -s <mag step>'
         stop
      end if

      do i = 1, n_max
         hfa(i) = 0.
         hfo(i) = 0.
      end do

      open (unit=42, file=listname, status='old')

 100  continue
      read (42, '(a)', end = 400) line

      call read_file_name (line, i1, i2, finished, 200)
      if (finished) stop
      dirname = line(i1:i2)
      ld = i2 - i1 + 1

      line = line(i2+1:)
      lp = 200 - i2
      call read_file_name (line, i1, i2, finished, lp)
      if (finished) stop
      pref = line(i1:i2)
      lf = i2 - i1 + 1

      filename = dirname(1:ld)//pref(1:lf)//'.comb.found'
      open (unit=17, file=filename, status='old', err=500)
 200  continue
         read (17, *, err=200, end=210) fx, fy, mag, fra, fangle
         i_mag = int((mag-mag_min)/mag_step) + 1
         if ((i_mag .gt. 0) .and. (i_mag .le. n_max)) then
            hfa(i_mag) = hfa(i_mag) + 1.
            hfo(i_mag) = hfo(i_mag) + 1.
         end if
         goto 200
 210  continue
      close (17)

      filename = dirname(1:ld)//pref(1:lf)//'.comb.missed'
      open (unit=18, file=filename, status='old', err=500)
 300  continue
         read (18, *, err=300, end=310) fx, fy, mag, fra, fangle
         i_mag = int((mag-mag_min)/mag_step) + 1
         if ((i_mag .gt. 0) .and. (i_mag .le. n_max)) then
            hfa(i_mag) = hfa(i_mag) + 1.
         end if
         goto 300
 310  continue
      close (18)

      goto 100

 400  continue
      close (42)

      call read_file_name (listname, i1, i2, finished, 80)
      filename = listname(i1:i2)//'.eff'
      open (unit=3, file=filename, status='unknown')
      do i = 1, n_max
         if (hfa(i) .gt. 0.) then
            frac = hfo(i)/hfa(i)
            sigma = sqrt(frac*(1.-frac)/nint(hfa(i)))
            write (3, '(2(1x,f5.2),1x,i4,2(1x,f5.2))')
     $        mag_min + (i-0.5)*mag_step, frac,
     $        nint(hfa(i)), min(sigma, 1.-frac), min(sigma, frac)
         end if
      end do
      close (3)

c Apparently things went right

      open (unit=1, file='global-pipe-eff.OK', status='unknown')
      write (1, *) ' '
      close (1)
      stop

 500  continue
      write (6, *) 'Could not find '//filename
      write (6, *) 'Skipping to next file.'
      goto 100

      end
